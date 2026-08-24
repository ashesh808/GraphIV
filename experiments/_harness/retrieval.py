"""
The committed retrieval recipe as one reusable call

Wrapping it here is what stopped every experiment from re-inlining the same five steps
The ancestor injection takes an optional cosine gate
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.core.store import Store
from graphiv.generate.pipeline import TIERS
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.recency import FrontierSpec, detect_frontier
from graphiv.retrieve.refined import frontier_pull
from graphiv.retrieve.subgraph import augment_with_ancestors, induce_subgraph


@dataclass
class Subgraph:
    landmarks: list[Landmark]
    edges: list[Edge]  # induced sub-edges among the landmarks
    pool: dict[str, PoolNode]  # the full candidate pool (for wider re-ranking / filtering)
    pool_edges: list[Edge]  # ALL induced edges among the pool (re-rank a wider top-K with this +
    # the same frontier spec so the wider list stays consistent with the top-m)
    frontier: FrontierSpec


def retrieve_subgraph(
    store: Store, qvec: list[float], q: str, *, gate: float = 0.30, m: int | None = None
) -> Subgraph:
    """
    Committed retrieval: hybrid pool + frontier pull + gated ancestor augmentation + PPR top-m

        `gate` is the shipped 0.30 ancestor cosine floor (02-03 sweep at 0.35
        Relaxed to 0.30 by the
        02-07 knob sweep — safe only with fast m>=60; 0 disables); `m` overrides the
        fast-tier landmark cap (e.g. a wider PPR window for a downstream relevance filter).
    """
    n_pool, _, m_default, _ = TIERS["fast"]
    m = m or m_default
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
    _ = augment_with_ancestors(store, pool, qvec, max_add=120, min_cosine=gate)
    edges = induce_subgraph(store, list(pool))
    lms = rank_landmarks_ppr(pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year)
    keep = {lm.arxiv_id for lm in lms}
    return Subgraph(lms, [e for e in edges if e.src in keep and e.dst in keep], pool, edges, fr)
