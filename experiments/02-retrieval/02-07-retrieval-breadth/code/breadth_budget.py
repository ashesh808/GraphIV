"""02-07 retrieval-breadth-and-budget: justify the shipped ef_search/floor/m package.

Six named conditions, each isolating ONE decision against its neighbors:
  A_old_shipped   ef=40   floor=0.35 m=40   (pre-fix production; reproduces the 02-06 ppr row)
  B_ef_fix        ef=1000 floor=0.35 m=40   (the bug fix alone -> pool-hit up, landmark-hit DOWN)
  C_floor_only    ef=1000 floor=0.30 m=40   (floor without budget -> gold dilution; why m rises)
  D_shipped       ef=1000 floor=0.30 m=60   (the shipped package; gate condition)
  E_paid_upgrade  ef=1000 floor=0.30 m=80   (documented cost/benefit; not shipped)
  F_floor_abl     ef=1000 floor=0.35 m=60   (floor ablation at shipped budget -> BYOL miss)

ef_search is session-SET per condition (Store now defaults to 1000; A resets to 40 to
reproduce the pgvector default that capped every KNN at 40 rows). Grades ride the shared
cache. Selection is the shipped fused-seeded PPR + frontier reservation throughout.
"""

import asyncio
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, LiteralString, cast

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

from _harness.topics import TOPICS, battery  # noqa: E402

from _common import PG_DSN  # noqa: E402
from pagerank import personalized_pagerank  # noqa: E402
from pipeline import _free_router_vram  # noqa: E402
from reader_grade import LABELS, Grade, candidates, fused_score, grade_many  # noqa: E402  # fmt: skip
from recency import FrontierSpec, detect_frontier, frontier_select  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402
from subgraph import Edge, Landmark, PoolNode, augment_with_ancestors, induce_subgraph  # noqa: E402  # fmt: skip

RESULTS = _EXP / "results"
N_POOL = 400

# (name, ef_search, ancestor floor, landmark budget m)
CONDITIONS: list[tuple[str, int, float, int]] = [
    ("A_old_shipped", 40, 0.35, 40),
    ("B_ef_fix", 1000, 0.35, 40),
    ("C_floor_only", 1000, 0.30, 40),
    ("D_shipped", 1000, 0.30, 60),
    ("E_paid_upgrade", 1000, 0.30, 80),
    ("F_floor_abl", 1000, 0.35, 60),
]

# adversarial litmus questions + must-have ids (mirrors 02-06; kept inline so this
# experiment reproduces standalone)
LITMUS: dict[str, tuple[str, list[str]]] = {
    "kv": (
        "Compare the frontier approaches to KV cache compression and memory-efficient "
        "attention for long-context LLM inference — quantization, token eviction/selection, "
        "paged and offloaded caches, and linear-attention hybrids: what are the measured "
        "memory/throughput/accuracy tradeoffs of each, and which techniques compose?",
        [
            "2306.14048",
            "2309.06180",
            "2401.18079",
            "2402.02750",
            "2406.10774",
            "2407.02490",
            "2410.10819",
            "2405.12981",
        ],
    ),
    "rl": (
        "As of 2026, compare reinforcement-learning-based post-training methods for LLM "
        "reasoning — PPO, DPO and its variants, GRPO, RLVR, and process reward models: sample "
        "efficiency, compute cost, measured benchmark gains, and known failure modes of each.",
        [
            "1707.06347",
            "2305.18290",
            "2402.03300",
            "2501.12948",
            "2305.20050",
            "2405.14734",
            "2402.01306",
            "2310.12036",
        ],
    ),
    "jepa": (
        "How has the Joint-Embedding Predictive Architecture (JEPA) paradigm evolved from "
        "its foundations to the current frontier: architectural innovations, latent-space "
        "prediction strategies, and applications across modalities?",
        ["2301.08243", "2404.08471", "2202.03555", "2006.07733", "2410.19560"],
    ),
}


def _fused_pool(
    pool: dict[str, PoolNode], grades: dict[str, Grade]
) -> dict[str, PoolNode]:
    out: dict[str, PoolNode] = {}
    for a, n in pool.items():
        g = grades.get(a)
        if g is not None and g.relevance <= -2:
            continue
        out[a] = PoolNode(
            n.arxiv_id, n.title, n.year, n.category, fused_score(n.score, g)
        )
    return out


def _select_ppr(
    fpool: dict[str, PoolNode], edges: list[Edge], fr: FrontierSpec, m: int
) -> tuple[list[str], dict[str, int]]:
    """Shipped selection (frontier reservation + fused-seeded PPR); returns chosen + full ranks."""
    lms = [
        Landmark(n.arxiv_id, n.title, n.year, n.category, n.score, 0)
        for n in fpool.values()
    ]
    reserved = [
        lm.arxiv_id for lm in frontier_select(lms, fr.frontier_year, fr.recent_floor)
    ]
    rest = {a: n for a, n in fpool.items() if a not in set(reserved)}
    seed = {a: max(n.score, 0.0) for a, n in rest.items()}
    ppr = personalized_pagerank(list(rest), edges, seed)
    order = sorted(rest, key=lambda a: ppr.get(a, 0.0), reverse=True)
    chosen = reserved + order[: max(0, m - len(reserved))]
    return chosen[:m], {a: i + 1 for i, a in enumerate(order)}


def run() -> None:
    keys = battery()
    gold = [k for k in keys if TOPICS[k].canonical]
    queries: dict[str, str] = {k: TOPICS[k].query for k in keys}
    for lk, (q, _) in LITMUS.items():
        queries[f"litmus_{lk}"] = q
    RESULTS.mkdir(parents=True, exist_ok=True)

    _free_router_vram()
    qvecs = {k: embed_query(q, mode="asym") for k, q in queries.items()}
    free_model()

    sets: dict[str, dict[str, list[str]]] = {c[0]: {} for c in CONDITIONS}
    pools: dict[tuple[str, str], set[str]] = {}
    all_grades: dict[str, dict[str, Grade]] = {}
    fr_n: dict[str, dict[str, int]] = {c[0]: {} for c in CONDITIONS}
    edge_d: dict[str, dict[str, float]] = {c[0]: {} for c in CONDITIONS}
    detail: dict[str, list[dict[str, Any]]] = {}  # pyright: ignore[reportExplicitAny]
    wall: dict[str, float] = {c[0]: 0.0 for c in CONDITIONS}

    # pool variants are shared across conditions: (ef, floor) -> per-topic build
    variants = sorted({(ef, fl) for _, ef, fl, _ in CONDITIONS})
    for key, q in queries.items():
        built: dict[
            tuple[int, float],
            tuple[dict[str, PoolNode], list[Edge], dict[str, int], FrontierSpec],
        ] = {}
        store = Store(PG_DSN, emb_space="asym")
        try:
            for ef, fl in variants:
                _ = store.conn.execute(
                    cast(LiteralString, f"SET hnsw.ef_search = {ef}")
                )
                t0 = time.monotonic()
                pool = hybrid_pool(store, qvecs[key], q, N_POOL)
                fr40 = detect_frontier(
                    [n.year for n in pool.values() if n.year is not None],
                    datetime.now().year,
                    datetime.now().month,
                    40,
                    0.4,
                )
                pool.update(
                    frontier_pull(store, qvecs[key], fr40.frontier_year, want=60)
                )
                _ = augment_with_ancestors(
                    store, pool, qvecs[key], max_add=120, min_cosine=fl
                )
                edges = induce_subgraph(store, list(pool))
                dt = time.monotonic() - t0
                indeg: dict[str, int] = {}
                for e in edges:
                    indeg[e.dst] = indeg.get(e.dst, 0) + 1
                built[(ef, fl)] = (pool, edges, indeg, fr40)
                for name, cef, cfl, _m in CONDITIONS:
                    if (cef, cfl) == (ef, fl):
                        wall[name] += dt
            # grade the superset once (largest m across conditions per variant)
            _ = store.conn.execute("SET hnsw.ef_search = 1000")
            cand_set: set[str] = set()
            union_pool: dict[str, PoolNode] = {}
            for (ef, fl), (pool, _e, indeg, _f) in built.items():
                m_max = max(
                    m for _, cef, cfl, m in CONDITIONS if (cef, cfl) == (ef, fl)
                )
                cand_set.update(candidates(pool, indeg, m_max))
                union_pool.update(pool)
            cand = [a for a in cand_set if a in union_pool]
            qhash = hashlib.sha1(q.encode()).hexdigest()[:12]
            abstracts = store.abstracts(cand)
            grades = asyncio.run(grade_many(q, qhash, union_pool, cand, abstracts))
            all_grades[key] = grades

            for name, ef, fl, m in CONDITIONS:
                pool, edges, indeg, fr40 = built[(ef, fl)]
                pools[(name, key)] = set(pool)
                fpool = _fused_pool(pool, grades)
                fr = FrontierSpec(
                    fr40.frontier_year, max(1, round(0.4 * m)), fr40.now_year
                )
                t0 = time.monotonic()
                chosen, rank_of = _select_ppr(fpool, edges, fr, m)
                wall[name] += time.monotonic() - t0
                sets[name][key] = chosen
                cs = set(chosen)
                year_of = {a: n.year for a, n in fpool.items()}
                fr_n[name][key] = sum(
                    1 for a in cs if (year_of.get(a) or 0) >= fr.frontier_year
                )
                edge_d[name][key] = sum(
                    1 for e in edges if e.src in cs and e.dst in cs
                ) / max(1, len(cs))
                if key.startswith("litmus_"):
                    lk = key.removeprefix("litmus_")
                    for aid in LITMUS[lk][1]:
                        g = grades.get(aid)
                        detail.setdefault(lk, []).append(
                            {
                                "condition": name,
                                "id": aid,
                                "in_pool": aid in pool,
                                "grade": f"{g.role}/{g.relevance:+d}" if g else None,
                                "ppr_rank": rank_of.get(aid),
                                "landmark": aid in cs,
                            }
                        )
        finally:
            store.close()
        print(
            f"[{key}] "
            + " ".join(f"{n}:{len(pools[(n, key)])}" for n, *_ in CONDITIONS),
            flush=True,
        )

    def agg(name: str) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        lmr, spr = [], []
        for k in gold:
            chosen = {a.lower() for a in sets[name][k]}
            canon = {c.lower() for c in TOPICS[k].canonical}
            spine = {s.lower() for s in TOPICS[k].spine}
            lmr.append(len(canon & chosen) / len(canon) if canon else 0.0)
            spr.append(len(spine & chosen) / len(spine) if spine else 0.0)
        per_topic: list[float] = []
        comp: Counter[str] = Counter()
        for k in queries:
            labs = [
                all_grades[k][a].role
                for a in sets[name][k]
                if a in all_grades[k] and all_grades[k][a].role in LABELS
            ]
            comp.update(labs)
            if labs:
                per_topic.append(1 - labs.count("unrelated") / len(labs))
        ph, lh, tot = 0, 0, 0
        for lk, (_, must) in LITMUS.items():
            kk = f"litmus_{lk}"
            pl = {a.lower() for a in pools[(name, kk)]}
            cs = {a.lower() for a in sets[name][kk]}
            for aid in must:
                tot += 1
                ph += aid.lower() in pl
                lh += aid.lower() in cs
        n = len(queries)
        cond = next(c for c in CONDITIONS if c[0] == name)
        return {
            "condition": name,
            "ef_search": cond[1],
            "floor": cond[2],
            "m": cond[3],
            "landmark_recall_gold3": round(sum(lmr) / len(lmr), 3),
            "spine_recall_gold3": round(sum(spr) / len(spr), 3),
            "relevance_rate": (
                round(sum(per_topic) / len(per_topic), 3) if per_topic else 0.0
            ),
            "litmus_pool_hit": round(ph / tot, 3),
            "litmus_landmark_hit": round(lh / tot, 3),
            "frontier_mean": round(sum(fr_n[name].values()) / n, 1),
            "edges_per_landmark": round(sum(edge_d[name].values()) / n, 2),
            "wall_seconds": round(wall[name], 1),
        }

    report = [agg(c[0]) for c in CONDITIONS]
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"conditions": report, "litmus_detail": detail}, indent=1)
    )
    cols = list(report[0].keys())
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in report]
    md = "\n".join(lines)
    _ = (RESULTS / "metrics.md").write_text(md + "\n")
    print("\n" + md, flush=True)


if __name__ == "__main__":
    run()
