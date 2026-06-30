"""Selection flags — per-paper relevance (-2..+2) of the landmark set under four selection arms.

Scores every selected paper on its salient full text (sum penalizes drift/noise; mean = per-paper
quality; count-independent). Arms isolate filter-type x count at cap 50: fixed50 (PPR top-50),
gate50 (0.35 cosine ancestor gate), llm50 (drop role<-2 over PPR-80, capped 50), llm_dyn (same
filter, soft cap 75). The ablation conclusion: the COUNT does not matter — cosine-gate and
LLM-filter are independent on/off flags. Scores cached by (topic, arxiv_id) in cache/cache.db.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[4]  # code -> NN-slug -> 02-retrieval -> experiments -> repo
for _p in (
    str(_REPO / "experiments"),
    str(_REPO / "phases"),
    str(_REPO / "phases" / "phase-6" / "components"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _harness._boot import JUDGE_MODEL  # noqa: E402
from _harness._llm import chat, parse_json  # noqa: E402
from _harness.retrieval import retrieve_subgraph  # noqa: E402
from _harness.topics import TOPICS, battery  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from _common import PG_DSN  # noqa: E402
from fulltext import extract_salient  # noqa: E402
from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import _free_router_vram  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402

GATE, CAND, CAP, DYN = 0.35, 80, 50, 75
ARMS = ("fixed50", "gate50", "llm50", "llm_dyn")
RESULTS = _EXP / "results"
CACHE = _EXP / "cache"

_SYS = (
    "Score how relevant a research paper is to a TOPIC: +2 = core/foundational to the topic; "
    "+1 = a clearly relevant contribution; 0 = borderline/tangential; -1 = weakly related / off-focus; "
    "-2 = unrelated (off-topic). Judge by what the paper is actually about (title + text). "
    'Output ONLY JSON: {"score": <integer -2..2>}.'
)


def _score(q: str, title: str, text: str) -> int:
    obj = parse_json(
        chat(
            JUDGE_MODEL,
            _SYS,
            f"TOPIC: {q}\n\nPAPER\ntitle: {title}\n{text[:4000]}",
            temperature=0.0,
            max_tokens=30,
        )
    )
    if not isinstance(obj, dict):
        return 0
    try:
        return max(-2, min(2, int(obj.get("score", 0))))
    except (TypeError, ValueError):
        return 0


def _cached(
    conn: sqlite3.Connection,
    topic: str,
    aid: str,
    title: str,
    abstract: str,
    use_cache: bool,
) -> int:
    if use_cache:
        row: tuple[int] | None = conn.execute(
            "SELECT sc FROM score WHERE topic=? AND arxiv_id=?", (topic, aid)
        ).fetchone()
        if row is not None:
            return row[0]
    sc = _score(TOPICS[topic].query, title, extract_salient(aid) or abstract)
    _ = conn.execute("INSERT OR REPLACE INTO score VALUES (?,?,?)", (topic, aid, sc))
    conn.commit()
    return sc


def _retrieve(keys: list[str]) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    _free_router_vram()
    for k in keys:
        qv = embed_query(TOPICS[k].query, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            ung = retrieve_subgraph(store, qv, TOPICS[k].query, gate=0.0, m=CAP)
            gat = retrieve_subgraph(store, qv, TOPICS[k].query, gate=GATE, m=CAP)
            fr = ung.frontier
            cand = rank_landmarks_ppr(
                ung.pool,
                ung.pool_edges,
                CAND,
                fr.frontier_year,
                fr.recent_floor,
                fr.now_year,
            )
            uids = {lm.arxiv_id for lm in cand} | {lm.arxiv_id for lm in gat.landmarks}
            absd = store.abstracts(list(uids))
        finally:
            store.close()
        data[k] = {"cand": cand, "gate50": gat.landmarks, "abs": absd}
        print(f"[retrieve] {k}: cand={len(cand)} gate={len(gat.landmarks)}", flush=True)
    free_model()
    return data


def _stats(scs: list[int]) -> tuple[int, float, int]:
    return (sum(scs), round(sum(scs) / len(scs), 3) if scs else 0.0, len(scs))


def run(use_cache: bool = True) -> None:
    keys = [k for k in (sys.argv[1:] or battery()) if k in TOPICS]
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE / "cache.db")
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS score (topic TEXT, arxiv_id TEXT, sc INT, PRIMARY KEY(topic, arxiv_id))"
    )
    conn.commit()

    data = _retrieve(keys)
    done = 0
    for k in keys:
        d = data[k]
        sc: dict[str, int] = {}
        for lm in (*d["cand"], *d["gate50"]):
            if lm.arxiv_id not in sc:
                sc[lm.arxiv_id] = _cached(
                    conn,
                    k,
                    lm.arxiv_id,
                    lm.title,
                    d["abs"].get(lm.arxiv_id, ""),
                    use_cache,
                )
                done += 1
                if done % 50 == 0:
                    print(f"[score] {done} papers", flush=True)
        d["sc"] = sc
        kept = [lm for lm in d["cand"] if sc.get(lm.arxiv_id, 0) > -2]
        d["sets"] = {
            "fixed50": d["cand"][:CAP],
            "gate50": d["gate50"],
            "llm50": kept[:CAP],
            "llm_dyn": kept[:DYN],
        }
    conn.close()

    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        st = [
            _stats([data[k]["sc"].get(lm.arxiv_id, 0) for lm in data[k]["sets"][arm]])
            for k in keys
        ]
        neg2 = sum(
            sum(
                1
                for lm in data[k]["sets"][arm]
                if data[k]["sc"].get(lm.arxiv_id, 0) == -2
            )
            for k in keys
        )
        rows.append(
            {
                "arm": arm,
                "count": round(sum(s[2] for s in st) / len(st), 1),
                "sum": round(sum(s[0] for s in st) / len(st), 2),
                "mean": round(sum(s[1] for s in st) / len(st), 3),
                "neg2_per_list": round(neg2 / len(keys), 2),
            }
        )
    _write_outputs(rows, len(keys))
    print("\n" + (RESULTS / "metrics.md").read_text(), flush=True)


# --- figure + latex tables (for report/report.tex) ---------------------------
def _write_outputs(rows: list[dict[str, Any]], n_topics: int) -> None:
    cols = ["arm", "count", "sum", "mean", "neg2_per_list"]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md.append(
        f"\n_per-paper relevance -2..+2 on salient text; sum (drift/noise penalized) + mean "
        f"(per-paper quality); {n_topics} topics; cap {CAP} (llm_dyn -> {DYN})._"
    )
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n")
    _ = (RESULTS / "metrics.json").write_text(json.dumps(rows, indent=1))
    bar_chart(
        rows,
        "arm",
        [
            ("sum", "relevance sum (mass)"),
            ("mean", "relevance mean (quality)"),
            ("neg2_per_list", "unrelated per list (lower better)"),
        ],
        RESULTS / "ablation.png",
        title=f"Selection arms over {n_topics} topics — filter lifts sum+mean; count (llm_dyn) lifts only sum",
    )
    macros = []
    for r in rows:
        tag = "".join(
            c for c in r["arm"] if c.isalpha()
        )  # letter-only: tex macro names
        macros.append(f"\\newcommand{{\\{tag}Sum}}{{{r['sum']}}}")
        macros.append(f"\\newcommand{{\\{tag}Mean}}{{{r['mean']}}}")
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n")
    show = [
        ("count", "count"),
        ("sum", "sum"),
        ("mean", "mean"),
        ("neg2_per_list", "unrel./list"),
    ]
    lines = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "arm & " + " & ".join(c[1] for c in show) + " \\\\",
        "\\midrule",
    ]
    for r in rows:
        lines.append(
            r["arm"].replace("_", r"\_")
            + " & "
            + " & ".join(str(r[c[0]]) for c in show)
            + " \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    run()
