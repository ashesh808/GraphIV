"""
The ancestor relevance gate: precision and recall of the ancestor injection

Ancestors are ranked by citer count before cosine, so fame beats relevance without a floor
This sweeps the floor to find where the recall plateau starts
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from _harness._boot import JUDGE_MODEL  # noqa: E402
from _harness._llm import chat, parse_json  # noqa: E402
from _harness.topics import TOPICS, battery  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from graphiv.core.embed import embed_query, free_model
from graphiv.core.models import PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store
from graphiv.generate.pipeline import TIERS, _free_router_vram
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.recency import detect_frontier
from graphiv.retrieve.refined import frontier_pull
from graphiv.retrieve.subgraph import induce_subgraph

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[4]  # code -> NN-slug -> 02-retrieval -> experiments -> repo

RESULTS = _EXP / "results"
# judgments are shared with 02-02 (role label is retrieval-independent); reuse its cache
CACHE_DB = _EXP.parent / "02-02-relevance-judge" / "cache" / "judge_cache.db"
LABELS = ("foundational", "core", "frontier", "peripheral", "unrelated")

"""
Each arm is a name, a cosine floor on injected ancestors, and whether to use the modal prefix
The grid exists because a floor from a coarse search could be a peak rather than a plateau
"""
VARIANTS: list[tuple[str, float, bool]] = [
    ("baseline", 0.0, False),
    ("floor25", 0.25, False),
    ("floor30", 0.30, False),
    ("floor35", 0.35, False),
    ("floor40", 0.40, False),
    ("floor45", 0.45, False),
]

_SYS = (
    "You categorize ONE research paper by its ROLE relative to a TOPIC and the body of work that "
    "stretches from it. You are given the topic and the paper's title, year, and abstract. Assign "
    "exactly one label:\n"
    "- foundational: a seminal/origin work the topic's methods are built upon; introduced a "
    "primitive the field now assumes.\n"
    "- core: a central, widely-built-on method or result in the topic's main line (load-bearing, "
    "but not the origin).\n"
    "- frontier: recent work pushing the leading edge — new capabilities, SOTA, or open directions.\n"
    "- peripheral: genuinely related but tangential — an application to an adjacent domain, or a "
    "survey/benchmark/tooling paper.\n"
    "- unrelated: off-topic for THIS specific topic; does not belong in a focused review of it.\n"
    "Judge by the paper's CONTENT vs the topic, not by fame; use the year only as a recency hint. "
    'Output ONLY JSON: {"label":"<one of the five>","reason":"<=160 chars"}.'
)


def modal_cat(pool: dict[str, PoolNode], core_ids: set[str], topn: int = 30) -> str | None:
    core = sorted((pool[a] for a in core_ids), key=lambda n: -n.score)[:topn]
    cnt = Counter(n.category for n in core if n.category)
    return cnt.most_common(1)[0][0] if cnt else None


def gated_landmarks(store: Store, qvec: list[float], q: str, floor: float, cat: bool) -> list[str]:
    """
    Committed retrieval, but the ancestor injection is filtered by cosine floor (+ optional cat)
    """
    n_pool, _, m, _ = TIERS["fast"]
    now = datetime.now()
    pool = hybrid_pool(store, qvec, q, n_pool)  # core: always kept
    core_ids = set(pool)
    fr = detect_frontier(
        [n.year for n in pool.values() if n.year is not None],
        now.year,
        now.month,
        m,
        0.4,
    )
    pool.update(
        frontier_pull(store, qvec, fr.frontier_year, want=60)
    )  # kept (cosine-gated already)
    catpfx = modal_cat(pool, core_ids) if cat else None
    for n in store.ancestors(list(pool), qvec, 120, 3, catpfx):  # GATED injection
        if n.arxiv_id in pool or n.score < floor:
            continue
        pool[n.arxiv_id] = n
    edges = induce_subgraph(store, list(pool))
    lms = rank_landmarks_ppr(pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year)
    return [lm.arxiv_id for lm in lms]


def judge(
    conn: sqlite3.Connection,
    topic: str,
    q: str,
    aid: str,
    title: str,
    year: int | None,
    abstract: str,
    use_cache: bool = True,
) -> str:
    row: tuple[str] | None = (
        conn.execute(
            "SELECT label FROM judge WHERE topic=? AND arxiv_id=?", (topic, aid)
        ).fetchone()
        if use_cache
        else None
    )
    if row is not None:
        return row[0]
    user = (
        f"TOPIC: {q}\n\nPAPER\ntitle: {title}\nyear: {year if year is not None else '?'}\n"
        f"arXiv: {aid}\nabstract: {abstract[:3000] or '(abstract unavailable)'}"
    )
    obj = parse_json(chat(JUDGE_MODEL, _SYS, user, temperature=0.0, max_tokens=300))
    label = str(obj.get("label", "")).strip().lower() if isinstance(obj, dict) else ""
    label = label if label in LABELS else "unparsed"
    _ = conn.execute(
        "INSERT OR REPLACE INTO judge VALUES (?,?,?,?)", (topic, aid, label, "(02-03)")
    )
    conn.commit()
    return label


def run(use_cache: bool = True) -> None:
    keys = battery()
    gold = [k for k in keys if TOPICS[k].canonical]
    out = RESULTS
    out.mkdir(parents=True, exist_ok=True)

    # stage 1: retrieve all variants x topics (nomic loaded once); collect landmark sets + meta
    sets: dict[str, dict[str, list[str]]] = {v[0]: {} for v in VARIANTS}
    meta: dict[str, tuple[str, int | None]] = {}
    abst: dict[str, dict[str, str]] = {}
    _free_router_vram()
    for key in keys:
        q = TOPICS[key].query
        qv = embed_query(q, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            need: set[str] = set()
            for name, floor, cat in VARIANTS:
                lms = gated_landmarks(store, qv, q, floor, cat)
                sets[name][key] = lms
                need.update(lms)
            rows: list[tuple[Any, ...]] = store.conn.execute(
                "SELECT arxiv_id, title, year FROM paper_meta WHERE arxiv_id = ANY(%s)",
                (list(need),),
            ).fetchall()
            for aid, title, year in rows:
                meta[str(aid)] = (
                    str(title or ""),
                    int(year) if year is not None else None,
                )
            abst[key] = store.abstracts(list(need))
        finally:
            store.close()
        print(
            f"[retrieve] {key}: " + " ".join(f"{n}={len(sets[n][key])}" for n, _, _ in VARIANTS),
            flush=True,
        )
    free_model()

    # stage 2: judge (cache-amortized across variants and the 02-02 run)
    conn = sqlite3.connect(CACHE_DB)
    labels: dict[tuple[str, str], str] = {}
    union = {(k, a) for name in sets for k in sets[name] for a in sets[name][k]}
    for i, (k, a) in enumerate(sorted(union)):
        title, year = meta.get(a, ("", None))
        labels[(k, a)] = judge(
            conn,
            k,
            TOPICS[k].query,
            a,
            title,
            year,
            abst.get(k, {}).get(a, ""),
            use_cache,
        )
        if (i + 1) % 50 == 0:
            print(f"[judge] {i + 1}/{len(union)}", flush=True)
    conn.close()

    # stage 3: score each variant
    def relevance(name: str) -> float:
        rates: list[float] = []
        for k in keys:
            labs = [labels[(k, a)] for a in sets[name][k] if labels[(k, a)] in LABELS]
            if labs:
                rates.append(1 - labs.count("unrelated") / len(labs))
        return round(sum(rates) / len(rates), 3) if rates else 0.0

    def unrel(name: str) -> float:
        labs = [labels[(k, a)] for k in keys for a in sets[name][k] if labels[(k, a)] in LABELS]
        return round(labs.count("unrelated") / len(labs), 3) if labs else 0.0

    def recall(name: str) -> tuple[float, float]:
        lmr: list[float] = []
        spr: list[float] = []
        for k in gold:
            chosen = {a.lower() for a in sets[name][k]}
            canon = {c.lower() for c in TOPICS[k].canonical}
            spine = {s.lower() for s in TOPICS[k].spine}
            lmr.append(len(canon & chosen) / len(canon) if canon else 0.0)
            spr.append(len(spine & chosen) / len(spine) if spine else 0.0)
        return round(sum(lmr) / len(lmr), 3), round(sum(spr) / len(spr), 3)

    report: list[dict[str, Any]] = []
    for name, floor, cat in VARIANTS:
        lm_rec, sp_rec = recall(name)
        report.append(
            {
                "variant": name,
                "floor": floor,
                "cat": cat,
                "relevance_rate_27": relevance(name),
                "unrelated_frac_27": unrel(name),
                "landmark_recall_gold3": lm_rec,
                "spine_recall_gold3": sp_rec,
            }
        )

    _ = (out / "metrics.json").write_text(json.dumps(report, indent=1))
    cols = [
        "variant",
        "floor",
        "cat",
        "relevance_rate_27",
        "unrelated_frac_27",
        "landmark_recall_gold3",
        "spine_recall_gold3",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in report:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    _ = (out / "metrics.md").write_text("\n".join(md) + "\n")
    _write_tex(report)
    bar_chart(
        report,
        "variant",
        [
            ("relevance_rate_27", "Precision / relevance (27 topics)"),
            ("landmark_recall_gold3", "Landmark recall (3 gold)"),
            ("spine_recall_gold3", "Spine recall (3 gold)"),
            ("unrelated_frac_27", "Unrelated fraction (lower better)"),
        ],
        out / "ablation.png",
        title="Ancestor cosine-floor sweep (0.25-0.45) — plateau vs peak around the 0.35 gate",
    )
    print("\n" + "\n".join(md), flush=True)


# --- latex tables (for report/report.tex) ------------------------------------
def _write_tex(report: list[dict[str, Any]]) -> None:
    f35 = next(r for r in report if r["variant"] == "floor35")
    base = next(r for r in report if r["variant"] == "baseline")
    macros = [
        f"\\newcommand{{\\baseRel}}{{{base['relevance_rate_27']}}}",
        f"\\newcommand{{\\floorRel}}{{{f35['relevance_rate_27']}}}",
        f"\\newcommand{{\\baseRec}}{{{base['landmark_recall_gold3']}}}",
        f"\\newcommand{{\\floorRec}}{{{f35['landmark_recall_gold3']}}}",
        f"\\newcommand{{\\floorSpine}}{{{f35['spine_recall_gold3']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n")
    show = [
        ("relevance_rate_27", "precision (27)"),
        ("unrelated_frac_27", "unrelated"),
        ("landmark_recall_gold3", "landmark rec. (3)"),
        ("spine_recall_gold3", "spine rec. (3)"),
    ]
    lines = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "variant & " + " & ".join(c[1] for c in show) + " \\\\",
        "\\midrule",
    ]
    for r in report:
        name = r["variant"].replace("_", r"\_")
        lines.append(name + " & " + " & ".join(str(r[c[0]]) for c in show) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    run()
