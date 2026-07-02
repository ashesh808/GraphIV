"""Hub-relevance sweep (structural pass) — which data-derived signal demotes generic hubs without
losing gold canonical papers. No blocklist. Arms re-rank the pool by ppr x a demotion factor; metrics
(gold recall = tripwire, mean global citers = popularity proxy, bg = background-ratio) are reported
per arm over the 27-topic battery. LLM oracle is a separate pass (hub_oracle.py).

    uv run python experiments/03-generation/03-11-hub-suppression/code/hub_sweep.py [topic ...]
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]
for _p in (
    str(_REPO / "experiments"),
    str(_REPO / "phases"),
    str(_REPO / "phases" / "phase-6" / "components"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _harness.retrieval import retrieve_subgraph  # noqa: E402
from _harness.topics import TOPICS, battery  # noqa: E402

from _common import PG_DSN  # noqa: E402
from pagerank import personalized_pagerank  # noqa: E402
from pipeline import _free_router_vram  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402

M = 40
OUT = _EXP / "results"
KEYS = [k for k in (sys.argv[1:] or battery()) if k in TOPICS]
# pop_bg{S}: demote ONLY papers that are both globally-popular AND background-cited HERE (topic-
# conditioned, strength S/10) -> protects load-bearing hubs (low bg) from the popularity penalty.
ARMS = ("none", "lift", "pr_ratio", "pop_bg3", "pop_bg5", "pop_bg7", "pop_bg10")


def _bg_ratio(pool_ids: list[str], pool_edges: list[Any]) -> dict[str, float | None]:
    inc: dict[str, int] = defaultdict(int)
    bg: dict[str, int] = defaultdict(int)
    for e in pool_edges:
        inc[e.dst] += 1
        if e.intent == "background":
            bg[e.dst] += 1
    return {a: (bg[a] / inc[a] if inc[a] else None) for a in pool_ids}


def _indeg(pool_ids: list[str], pool_edges: list[Any]) -> dict[str, int]:
    d: dict[str, int] = defaultdict(int)
    for e in pool_edges:
        d[e.dst] += 1
    return {a: d[a] for a in pool_ids}


def arm_score(arm: str, ppr: float, gc: int, lift: float, bg: float | None) -> float:
    """Re-rank score for one paper under one demotion arm (ppr x arm-specific factor)."""
    liftf = math.log1p(lift)
    prpen = 1.0 / (
        1.0 + math.log10(1 + gc)
    )  # demote by global popularity (topic-blind)
    pop = min(1.0, math.log10(1 + gc) / 5.0)  # saturating popularity, ~1 at 100k cites
    bgr = bg if bg is not None else 0.0
    if arm == "lift":
        return ppr * liftf
    if arm == "pr_ratio":
        return ppr * prpen
    if arm.startswith("pop_bg"):  # demote iff popular AND background-cited here
        s = int(arm[len("pop_bg") :]) / 10.0
        return ppr * (1.0 - s * bgr * pop)
    return ppr


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    store0 = Store(PG_DSN, emb_space="asym")
    row = store0.conn.execute("SELECT count(*) FROM paper").fetchone()
    n_papers = int(cast(int, row[0])) if row else 0
    store0.close()
    print(f"[hub] N={n_papers} topics={len(KEYS)}", flush=True)

    per: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    drops: dict[str, dict[str, int]] = {}
    sets_out: dict[str, dict[str, list[str]]] = {}
    meta_out: dict[str, dict[str, Any]] = {}
    _free_router_vram()
    for k in KEYS:
        q = TOPICS[k].query
        qv = embed_query(q, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            sg = retrieve_subgraph(store, qv, q, m=M)
            pool_ids = list(sg.pool)
            ppr = personalized_pagerank(
                pool_ids,
                sg.pool_edges,
                {a: max(sg.pool[a].score, 0.0) for a in pool_ids},
            )
            gc = store.global_citations(pool_ids)
        finally:
            store.close()
        indeg = _indeg(pool_ids, sg.pool_edges)
        bg = _bg_ratio(pool_ids, sg.pool_edges)
        npool = len(pool_ids)
        # lift = P(cited|topic) / P(cited)
        lift = {
            a: ((indeg[a] / npool) / ((gc.get(a, 0) + 1) / n_papers)) for a in pool_ids
        }
        canon = {c.lower() for c in TOPICS[k].canonical}
        sets: dict[str, list[str]] = {}
        for arm in ARMS:
            ranked = sorted(
                pool_ids,
                key=lambda a: arm_score(
                    arm, ppr.get(a, 0.0), gc.get(a, 0), lift[a], bg[a]
                ),
                reverse=True,
            )
            sel = ranked[:M]
            sets[arm] = sel
            recall = (
                len(canon & {a.lower() for a in sel}) / len(canon) if canon else None
            )
            mean_gc = sum(gc.get(a, 0) for a in sel) / len(sel)
            bgs = [b for a in sel if (b := bg[a]) is not None]
            per[arm].append(
                {
                    "topic": k,
                    "recall": recall,
                    "mean_gc": mean_gc,
                    "bg": sum(bgs) / len(bgs) if bgs else 0.0,
                }
            )
        sets_out[k] = sets
        union = {a for s in sets.values() for a in s}
        meta_out[k] = {
            a: {
                "title": sg.pool[a].title,
                "gc": gc.get(a, 0),
                "indeg": indeg[a],
                "bg": bg[a],
                "lift": round(lift[a], 1),
            }
            for a in union
        }
        dropped = set(sets["none"]) - set(sets["pop_bg7"])
        drops[k] = {
            a: gc.get(a, 0) for a in sorted(dropped, key=lambda a: -gc.get(a, 0))[:8]
        }
        print(
            f"[{k}] pool={npool} | none mean_gc={per['none'][-1]['mean_gc']:.0f} pop_bg7 mean_gc={per['pop_bg7'][-1]['mean_gc']:.0f}",
            flush=True,
        )
    free_model()

    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        rs = [r["recall"] for r in per[arm] if r["recall"] is not None]
        rows.append(
            {
                "arm": arm,
                "gold_recall": round(sum(rs) / len(rs), 3) if rs else 0.0,
                "mean_global_citers": round(
                    sum(r["mean_gc"] for r in per[arm]) / len(per[arm]), 1
                ),
                "bg_mean": round(sum(r["bg"] for r in per[arm]) / len(per[arm]), 3),
            }
        )
    cols = ["arm", "gold_recall", "mean_global_citers", "bg_mean"]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    _ = (OUT / "structural.md").write_text("\n".join(md) + "\n")
    _ = (OUT / "structural.json").write_text(
        json.dumps(
            {
                "rows": rows,
                "per_topic": per,
                "drops": drops,
                "sets": sets_out,
                "meta": meta_out,
            },
            indent=1,
        )
    )
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    main()
