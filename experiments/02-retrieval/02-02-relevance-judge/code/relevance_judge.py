"""
Precision and composition of the retrieved subgraph, which recall cannot see

It needs no gold, so unlike 02-01 it runs over the whole topic battery
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from _harness._boot import JUDGE_MODEL  # noqa: E402
from _harness._llm import chat, parse_json  # noqa: E402
from _harness.topics import TOPICS, battery  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from graphiv.core.embed import embed_query, free_model
from graphiv.core.models import Edge, PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store
from graphiv.generate.pipeline import TIERS, _free_router_vram
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.recency import detect_frontier
from graphiv.retrieve.refined import frontier_pull
from graphiv.retrieve.subgraph import augment_with_ancestors, induce_subgraph

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[4]  # code -> NN-slug -> 02-retrieval -> experiments -> repo

RESULTS = _EXP / "results"
CACHE = _EXP / "cache"
LABELS = ("foundational", "core", "frontier", "peripheral", "unrelated")

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


def _judge(topic_q: str, title: str, year: int | None, aid: str, abstract: str) -> dict[str, str]:
    user = (
        f"TOPIC: {topic_q}\n\nPAPER\ntitle: {title}\nyear: {year if year is not None else '?'}\n"
        f"arXiv: {aid}\nabstract: {abstract[:3000] or '(abstract unavailable)'}"
    )
    obj = parse_json(chat(JUDGE_MODEL, _SYS, user, temperature=0.0, max_tokens=300))
    label = str(obj.get("label", "")).strip().lower() if isinstance(obj, dict) else ""
    reason = str(obj.get("reason", ""))[:160] if isinstance(obj, dict) else ""
    if label not in LABELS:  # one retry on an off-menu / unparseable label
        obj = parse_json(chat(JUDGE_MODEL, _SYS, user, temperature=0.0, max_tokens=300))
        label = str(obj.get("label", "")).strip().lower() if isinstance(obj, dict) else ""
        reason = str(obj.get("reason", ""))[:160] if isinstance(obj, dict) else reason
    return {"label": label if label in LABELS else "unparsed", "reason": reason}


# --- committed retrieval (induce/PPR), same as 02-01 ------------------
def landmarks_for(store: Store, qvec: list[float], q: str) -> tuple[list[PoolNode], dict[str, int]]:
    n_pool, _, m, _ = TIERS["fast"]
    now = datetime.now()
    pool = hybrid_pool(store, qvec, q, n_pool)
    fr = detect_frontier(
        [n.year for n in pool.values() if n.year is not None],
        now.year,
        now.month,
        m,
        0.4,
    )
    pool.update(frontier_pull(store, qvec, fr.frontier_year, want=60))
    _ = augment_with_ancestors(store, pool, qvec, max_add=120)
    edges: list[Edge] = induce_subgraph(store, list(pool))
    lms = rank_landmarks_ppr(pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year)
    chosen = {lm.arxiv_id for lm in lms}
    indeg: dict[str, int] = defaultdict(int)
    for e in edges:
        if e.src in chosen and e.dst in chosen:
            indeg[e.dst] += 1
    nodes = [pool[a] for a in chosen if a in pool]
    return nodes, indeg


# --- cache -------------------------------------------------------------------
def _cache(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS judge "
        "(topic TEXT, arxiv_id TEXT, label TEXT, reason TEXT, PRIMARY KEY(topic, arxiv_id))"
    )
    conn.commit()
    return conn


def run(use_cache: bool = True) -> None:
    keys = battery()
    out = RESULTS
    out.mkdir(parents=True, exist_ok=True)
    cache = _cache(CACHE / "judge_cache.db")

    # --- stage 1: retrieve every topic's landmarks (nomic loaded once) --------
    plan: dict[str, list[tuple[str, str, int | None]]] = {}  # topic -> [(aid, title, year)]
    indeg_all: dict[str, dict[str, int]] = {}
    abstracts_all: dict[str, dict[str, str]] = {}
    _free_router_vram()
    for key in keys:
        q = TOPICS[key].query
        qv = embed_query(q, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            nodes, indeg = landmarks_for(store, qv, q)
            abstracts_all[key] = store.abstracts([n.arxiv_id for n in nodes])
        finally:
            store.close()
        plan[key] = [(n.arxiv_id, n.title, n.year) for n in nodes]
        indeg_all[key] = indeg
        print(f"[retrieve] {key}: {len(nodes)} landmarks", flush=True)
    free_model()  # unload nomic; router will serve the judge model on first call

    # --- stage 2: judge every landmark (cached/resumable) ---------------------
    raw: list[dict[str, Any]] = []
    total = sum(len(v) for v in plan.values())
    done = 0
    for key in keys:
        q = TOPICS[key].query
        for aid, title, year in plan[key]:
            row: tuple[str, str] | None = (
                cache.execute(
                    "SELECT label, reason FROM judge WHERE topic=? AND arxiv_id=?",
                    (key, aid),
                ).fetchone()
                if use_cache
                else None
            )
            if row is None:
                res = _judge(q, title, year, aid, abstracts_all[key].get(aid, ""))
                _ = cache.execute(
                    "INSERT OR REPLACE INTO judge VALUES (?,?,?,?)",
                    (key, aid, res["label"], res["reason"]),
                )
                cache.commit()
                label, reason = res["label"], res["reason"]
            else:
                label, reason = row[0], row[1]
            raw.append(
                {
                    "topic": key,
                    "arxiv_id": aid,
                    "year": year,
                    "in_degree": indeg_all[key].get(aid, 0),
                    "label": label,
                    "reason": reason,
                }
            )
            done += 1
            if done % 25 == 0:
                print(f"[judge] {done}/{total}", flush=True)
    cache.close()

    # --- aggregate -----------------------------------------------------------
    per_topic: list[dict[str, Any]] = []
    for key in keys:
        rows = [r for r in raw if r["topic"] == key]
        parsed = [r for r in rows if r["label"] in LABELS]
        n = len(parsed)
        counts = {lab: sum(1 for r in parsed if r["label"] == lab) for lab in LABELS}
        rel = round((n - counts["unrelated"]) / n, 3) if n else 0.0
        span = 1 if counts["foundational"] >= 1 and counts["frontier"] >= 1 else 0
        pt: dict[str, Any] = {
            "topic": key,
            "n": len(rows),
            "relevance_rate": rel,
            "lineage_span": span,
        }
        for lab in LABELS:
            pt[f"frac_{lab}"] = round(counts[lab] / n, 3) if n else 0.0
        per_topic.append(pt)

    def _mean(field: str) -> float:
        vals = [float(p[field]) for p in per_topic]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    indeg_by_label: dict[str, list[int]] = defaultdict(list)
    for r in raw:
        if r["label"] in LABELS:
            indeg_by_label[r["label"]].append(int(r["in_degree"]))
    overall: dict[str, Any] = {
        "n_topics": len(keys),
        "n_landmarks": len(raw),
        "relevance_rate": _mean("relevance_rate"),
        "lineage_span_frac": _mean("lineage_span"),
    }
    for lab in LABELS:
        overall[f"frac_{lab}"] = _mean(f"frac_{lab}")
        ds = indeg_by_label.get(lab, [])
        overall[f"indeg_{lab}"] = round(sum(ds) / len(ds), 2) if ds else 0.0

    _ = (out / "metrics_raw.json").write_text(json.dumps(raw, indent=1))
    _ = (out / "metrics.json").write_text(
        json.dumps({"overall": overall, "per_topic": per_topic}, indent=1)
    )
    cols = [
        "topic",
        "n",
        "relevance_rate",
        "lineage_span",
        *[f"frac_{lab}" for lab in LABELS],
    ]
    md = [
        "## overall",
        "",
        "```",
        json.dumps(overall, indent=1),
        "```",
        "",
        "## per topic",
        "",
    ]
    md.append("| " + " | ".join(cols) + " |")
    md.append("| " + " | ".join("---" for _ in cols) + " |")
    for p in per_topic:
        md.append("| " + " | ".join(str(p.get(c, "")) for c in cols) + " |")
    _ = (out / "metrics.md").write_text("\n".join(md) + "\n")
    _write_outputs(overall)
    print(
        f"\n[done] {out}/metrics.md  (relevance_rate={overall['relevance_rate']}, "
        f"lineage_span={overall['lineage_span_frac']}, {len(keys)} topics)",
        flush=True,
    )


# --- figure + latex tables (for report/report.tex) ---------------------------
def _write_outputs(overall: dict[str, Any]) -> None:
    rows = [
        {
            "role": lab,
            "frac": overall[f"frac_{lab}"],
            "indeg": overall[f"indeg_{lab}"],
        }
        for lab in LABELS
    ]
    bar_chart(
        rows,
        "role",
        [("frac", "fraction of landmarks"), ("indeg", "mean in-degree")],
        RESULTS / "ablation.png",
        title=(
            "Landmark role composition over 27 topics — "
            f"relevance={overall['relevance_rate']}, unrelated carries in-degree {overall['indeg_unrelated']}"
        ),
    )
    macros = [
        f"\\newcommand{{\\relRate}}{{{overall['relevance_rate']}}}",
        f"\\newcommand{{\\unrelFrac}}{{{overall['frac_unrelated']}}}",
        f"\\newcommand{{\\lineageSpan}}{{{overall['lineage_span_frac']}}}",
        f"\\newcommand{{\\indegUnrel}}{{{overall['indeg_unrelated']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n")
    lines = [
        "\\begin{tabular}{lrr}",
        "\\toprule",
        "role & fraction & mean in-degree \\\\",
        "\\midrule",
    ]
    for lab in LABELS:
        lines.append(f"{lab} & {overall[f'frac_{lab}']} & {overall[f'indeg_{lab}']} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    run()
