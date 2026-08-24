"""
The selection objective on trial, with PPR entered as a contestant

Six arms select the same budget over an identical front end, so only the objective differs
A review needs a covering set, while item-wise ranking optimizes for the single best page
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from _harness.topics import TOPICS, battery  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from graphiv.core.embed import embed_query, free_model
from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store
from graphiv.generate.pipeline import TIERS, _free_router_vram
from graphiv.retrieve.grade import LABELS, Grade, candidates, fused_score, grade_many
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.landmarks import (
    kmeans_labels,
    pool_coverage,
    select_facility,
    select_fused_topk,
    select_mmr,
    select_ppr,
    select_ppr_facility,
    select_proportional,
    unit_matrix,
)
from graphiv.retrieve.recency import FrontierSpec, detect_frontier, frontier_select
from graphiv.retrieve.refined import frontier_pull
from graphiv.retrieve.subgraph import augment_with_ancestors, induce_subgraph

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

RESULTS = _EXP / "results"
ARMS = ("ppr", "fused_topk", "mmr", "facility", "ppr_facility", "proportional")

# litmus questions and their must-have papers, checked at the pool and landmark boundaries
LITMUS: dict[str, tuple[str, list[str]]] = {
    "kv": (
        "Compare the frontier approaches to KV cache compression and memory-efficient "
        "attention for long-context LLM inference — quantization, token eviction/selection, "
        "paged and offloaded caches, and linear-attention hybrids: what are the measured "
        "memory/throughput/accuracy tradeoffs of each, and which techniques compose?",
        [
            "2306.14048",  # H2O
            "2309.06180",  # PagedAttention/vLLM
            "2401.18079",  # KVQuant
            "2402.02750",  # KIVI
            "2406.10774",  # Quest, dropped by the writer in the wild and by selection here
            "2407.02490",  # MInference
            "2410.10819",  # DuoAttention
            "2405.12981",  # CLA
        ],
    ),
    "rl": (
        "As of 2026, compare reinforcement-learning-based post-training methods for LLM "
        "reasoning — PPO, DPO and its variants, GRPO, RLVR, and process reward models: sample "
        "efficiency, compute cost, measured benchmark gains, and known failure modes of each.",
        [
            "1707.06347",  # PPO
            "2305.18290",  # DPO
            "2402.03300",  # DeepSeekMath / GRPO
            "2501.12948",  # DeepSeek-R1
            "2305.20050",  # Let's Verify Step by Step (PRM)
            "2405.14734",  # SimPO (missed in the wild)
            "2402.01306",  # KTO (missed in the wild)
            "2310.12036",  # IPO/GPO
        ],
    ),
    "jepa": (
        "How has the Joint-Embedding Predictive Architecture (JEPA) paradigm evolved from "
        "its foundations to the current frontier: architectural innovations, latent-space "
        "prediction strategies, and applications across modalities?",
        [
            "2301.08243",  # I-JEPA
            "2404.08471",  # V-JEPA (video feature prediction)
            "2202.03555",  # data2vec
            "2006.07733",  # BYOL
            "2410.19560",  # C-JEPA
        ],
    ),
}


def committed_pool(
    store: Store, qvec: list[float], q: str
) -> tuple[dict[str, PoolNode], list[Edge], FrontierSpec, int]:
    """
    Shipped committed retrieval (fast tier), shared by every arm
    """
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
    _ = augment_with_ancestors(store, pool, qvec, max_add=120, min_cosine=0.35)
    edges = induce_subgraph(store, list(pool))
    return pool, edges, fr, m


def fused_pool(pool: dict[str, PoolNode], grades: dict[str, Grade]) -> dict[str, PoolNode]:
    """
    Production fusion: fused score in .score, relevance -2 excluded (kept as connectors)
    """
    out: dict[str, PoolNode] = {}
    for a, n in pool.items():
        g = grades.get(a)
        if g is not None and g.relevance <= -2:
            continue
        out[a] = PoolNode(n.arxiv_id, n.title, n.year, n.category, fused_score(n.score, g))
    return out


def arm_landmarks(
    arm: str,
    fpool: dict[str, PoolNode],
    edges: list[Edge],
    embs: dict[str, list[float]],
    fr: FrontierSpec,
    m: int,
) -> list[str]:
    """
    Frontier reservation first (settled policy), then the arm fills the remainder
    """
    lms = [Landmark(n.arxiv_id, n.title, n.year, n.category, n.score, 0) for n in fpool.values()]
    reserved = [lm.arxiv_id for lm in frontier_select(lms, fr.frontier_year, fr.recent_floor)]
    taken = set(reserved)
    want = m - len(reserved)
    rest = {a: n for a, n in fpool.items() if a not in taken}
    if arm == "ppr":
        picks = select_ppr(rest, edges, want)
    elif arm == "fused_topk":
        picks = select_fused_topk(rest, want)
    elif arm == "mmr":
        picks = select_mmr(rest, embs, want)
    elif arm == "facility":
        picks = select_facility(rest, embs, want)
    elif arm == "ppr_facility":
        picks = select_ppr_facility(rest, edges, embs, want)
    else:
        picks = select_proportional(rest, embs, want)
    return reserved + picks


def cluster_recall(
    landmark_ids: list[str],
    fpool: dict[str, PoolNode],
    embs: dict[str, list[float]],
    k: int,
) -> float:
    """
    Fraction of fused-mass-carrying k-means clusters that got >=1 landmark
    """
    ids, mat = unit_matrix(fpool, embs)
    if not ids:
        return 0.0
    labels = kmeans_labels(mat, k)
    fused = np.array([fpool[a].score for a in ids], dtype=np.float32)
    lm_set = set(landmark_ids)
    hit, total = 0, 0
    for c in range(labels.max() + 1):
        members = [i for i in range(len(ids)) if labels[i] == c]
        if not members or float(np.clip(fused[members], 0, None).sum()) < 0.5:
            continue
        total += 1
        if any(ids[i] in lm_set for i in members):
            hit += 1
    return hit / total if total else 0.0


def run() -> None:
    keys = battery()
    gold = [k for k in keys if TOPICS[k].canonical]
    RESULTS.mkdir(parents=True, exist_ok=True)
    queries: dict[str, str] = {k: TOPICS[k].query for k in keys}
    for lk, (q, _) in LITMUS.items():
        queries[f"litmus_{lk}"] = q

    _free_router_vram()
    qvecs = {k: embed_query(q, mode="asym") for k, q in queries.items()}
    free_model()

    sets: dict[str, dict[str, list[str]]] = {a: {} for a in ARMS}
    all_grades: dict[str, dict[str, Grade]] = {}
    pools: dict[str, dict[str, PoolNode]] = {}
    times: dict[str, float] = dict.fromkeys(ARMS, 0.0)
    cover: dict[str, dict[str, float]] = {a: {} for a in ARMS}
    clrec: dict[str, dict[str, float]] = {a: {} for a in ARMS}
    edge_density: dict[str, dict[str, float]] = {a: {} for a in ARMS}
    frontier_n: dict[str, dict[str, int]] = {a: {} for a in ARMS}

    for key, q in queries.items():
        store = Store(PG_DSN, emb_space="asym")
        try:
            pool, edges, fr, m = committed_pool(store, qvecs[key], q)
            indeg: dict[str, int] = {}
            for e in edges:
                indeg[e.dst] = indeg.get(e.dst, 0) + 1
            cand = candidates(pool, indeg, m)
            qhash = hashlib.sha1(q.encode()).hexdigest()[:12]
            abstracts = store.abstracts(cand)
            grades = asyncio.run(grade_many(q, qhash, pool, cand, abstracts))
            fpool = fused_pool(pool, grades)
            embs = store.embeddings(list(fpool))
        finally:
            store.close()
        all_grades[key], pools[key] = grades, pool
        year_of = {a: n.year for a, n in fpool.items()}
        edge_pairs = [(e.src, e.dst) for e in edges]
        for arm in ARMS:
            t0 = time.monotonic()
            chosen = arm_landmarks(arm, fpool, edges, embs, fr, m)
            times[arm] += time.monotonic() - t0
            sets[arm][key] = chosen
            cs = set(chosen)
            cover[arm][key] = pool_coverage(chosen, fpool, embs, min_score=0.15)
            clrec[arm][key] = cluster_recall(chosen, fpool, embs, k=max(2, m // 8))
            edge_density[arm][key] = sum(1 for s, d in edge_pairs if s in cs and d in cs) / max(
                1, len(cs)
            )
            frontier_n[arm][key] = sum(1 for a in cs if (year_of.get(a) or 0) >= fr.frontier_year)
        print(
            f"[{key}] pool {len(pool)} graded {len(grades)} · "
            + " ".join(f"{a}={len(sets[a][key])}" for a in ARMS),
            flush=True,
        )

    def recall(arm: str) -> tuple[float, float]:
        lmr, spr = [], []
        for k in gold:
            chosen = {a.lower() for a in sets[arm][k]}
            canon = {c.lower() for c in TOPICS[k].canonical}
            spine = {s.lower() for s in TOPICS[k].spine}
            lmr.append(len(canon & chosen) / len(canon) if canon else 0.0)
            spr.append(len(spine & chosen) / len(spine) if spine else 0.0)
        return round(sum(lmr) / len(lmr), 3), round(sum(spr) / len(spr), 3)

    def rates(arm: str) -> tuple[float, Counter[str]]:
        per_topic: list[float] = []
        comp: Counter[str] = Counter()
        for k in keys:
            labs = [
                all_grades[k][a].role
                for a in sets[arm][k]
                if a in all_grades[k] and all_grades[k][a].role in LABELS
            ]
            comp.update(labs)
            if labs:
                per_topic.append(1 - labs.count("unrelated") / len(labs))
        return (round(sum(per_topic) / len(per_topic), 3) if per_topic else 0.0), comp

    def litmus(arm: str) -> tuple[float, float]:
        pool_hits, lm_hits, total = 0, 0, 0
        for lk, (_, must) in LITMUS.items():
            key = f"litmus_{lk}"
            pl = {a.lower() for a in pools[key]}
            cs = {a.lower() for a in sets[arm][key]}
            for aid in must:
                total += 1
                pool_hits += aid.lower() in pl
                lm_hits += aid.lower() in cs
        return round(pool_hits / total, 3), round(lm_hits / total, 3)

    report: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    n_topics = len(queries)
    for arm in ARMS:
        lm_rec, sp_rec = recall(arm)
        rel, comp = rates(arm)
        pool_hit, lm_hit = litmus(arm)
        total_roles = sum(comp.values()) or 1
        report.append(
            {
                "arm": arm,
                "landmark_recall_gold3": lm_rec,
                "spine_recall_gold3": sp_rec,
                "relevance_rate": rel,
                "pool_coverage": round(sum(cover[arm].values()) / n_topics, 3),
                "cluster_recall": round(sum(clrec[arm].values()) / n_topics, 3),
                "litmus_pool_hit": pool_hit,
                "litmus_landmark_hit": lm_hit,
                "frontier_mean": round(sum(frontier_n[arm].values()) / n_topics, 1),
                "edges_per_landmark": round(sum(edge_density[arm].values()) / n_topics, 2),
                "select_seconds": round(times[arm], 1),
                **{f"frac_{r}": round(comp[r] / total_roles, 3) for r in LABELS},
            }
        )

    _ = (RESULTS / "metrics.json").write_text(json.dumps(report, indent=1))
    cols = [
        "arm",
        "landmark_recall_gold3",
        "spine_recall_gold3",
        "relevance_rate",
        "pool_coverage",
        "cluster_recall",
        "litmus_pool_hit",
        "litmus_landmark_hit",
        "frontier_mean",
        "edges_per_landmark",
        "select_seconds",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in report:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n")
    bar_chart(
        report,
        "arm",
        [
            ("landmark_recall_gold3", "Landmark recall (3 gold) — the gate"),
            ("pool_coverage", "Pool coverage (fused-weighted)"),
            ("litmus_landmark_hit", "Litmus landmark hits (named papers)"),
            ("edges_per_landmark", "Edges per landmark (story health)"),
        ],
        RESULTS / "ablation.png",
        title="Selection objective on trial — PPR vs set-coverage arms",
    )
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    run()
