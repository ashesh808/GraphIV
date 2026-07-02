"""Canonical subgraph retrieval for experiments — the committed recipe as one reusable call.

Wraps the phase-6 retrieval components (hybrid pool -> frontier pull -> ancestor augmentation ->
induce -> PPR) so experiments stop re-inlining it (it was copy-pasted across every scratchpad this
session). Optional cosine `gate` on the ancestor injection (the exp-16 floor). Returns landmarks +
induced sub-edges + the full pool + frontier spec — callers that need a wider PPR window or a
precision filter (e.g. the landmark-selection experiment) reuse `pool`/`frontier`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# force the sys.path bootstrap before importing phase-6 modules by bare name
from ._boot import REPO as _REPO  # noqa: F401

from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import TIERS  # noqa: E402
from recency import FrontierSpec, detect_frontier  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from store import Store  # noqa: E402
from subgraph import Edge, Landmark, PoolNode, augment_with_ancestors, induce_subgraph  # noqa: E402  # fmt: skip


@dataclass
class Subgraph:
    landmarks: list[Landmark]
    edges: list[Edge]  # induced sub-edges among the landmarks
    pool: dict[
        str, PoolNode
    ]  # the full candidate pool (for wider re-ranking / filtering)
    pool_edges: list[
        Edge
    ]  # ALL induced edges among the pool (re-rank a wider top-K with this +
    # the same frontier spec so the wider list stays consistent with the top-m)
    frontier: FrontierSpec


def retrieve_subgraph(
    store: Store, qvec: list[float], q: str, *, gate: float = 0.35, m: int | None = None
) -> Subgraph:
    """Committed retrieval: hybrid pool + frontier pull + gated ancestor augmentation + PPR top-m.

    `gate` is the shipped 0.35 ancestor cosine floor (02-03 sweep; 0 disables); `m` overrides the
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
    lms = rank_landmarks_ppr(
        pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
    )
    keep = {lm.arxiv_id for lm in lms}
    return Subgraph(
        lms, [e for e in edges if e.src in keep and e.dst in keep], pool, edges, fr
    )
