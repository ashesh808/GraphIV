"""B2' — refined topic-graph retrieval (per checkpoint decisions).

Replaces the coarse arXiv-group anchor with topic-LEAF membership (recovers
interdisciplinary papers the group filter drops), then strengthens the pool with two
leaf-sourced, structure-preserving additions:

  - citation-aware drill: only add leaf members that have a CITES edge to the current
    pool (fixes the 0-edge collapse + the off-topic-drill bug from naive similarity drill).
  - recency injection: add recent (>= min_year) leaf members scored by similarity, so the
    frontier becomes retrievable (W2 is a retrieval problem, not a ranking one). `min_year` is
    the topic-adaptive frontier cutoff detected upstream, not a fixed year.

All additions come from the home leaf, so they stay on-topic by construction.
"""

from __future__ import annotations

from recency import frontier_select
from store import Store
from subgraph import PoolNode
from topic_anchor import TopicTree, anchor_keep, dominant_leaf


def citation_aware_drill(
    store: Store, qvec: list[float], pool_ids: set[str], members: list[str], target: int
) -> dict[str, PoolNode]:
    """Add leaf members that cite or are cited by the pool, scored by similarity."""
    if len(pool_ids) >= target:
        return {}
    cand = [m for m in members if m not in pool_ids]
    if not cand:
        return {}
    drilled = store.drill(cand, list(pool_ids), qvec, max(0, target - len(pool_ids)))
    return {n.arxiv_id: n for n in drilled}


def recency_inject(
    store: Store,
    qvec: list[float],
    pool_ids: set[str],
    members: list[str],
    k: int,
    min_year: int,
) -> dict[str, PoolNode]:
    """Add the top-`k` recent (>= min_year) leaf members by similarity to the query."""
    cand = [m for m in members if m not in pool_ids]
    if not cand or k <= 0:
        return {}
    nodes = store.recent_members(cand, qvec, min_year)
    # newest-cohort-first so the injected recent papers aren't all just-past-cutoff years
    picked = frontier_select(nodes, min_year, k)
    return {n.arxiv_id: n for n in picked}


def frontier_pull(
    store: Store,
    qvec: list[float],
    frontier_year: int,
    want: int = 60,
    probe: int = 1500,
) -> dict[str, PoolNode]:
    """Vector-search recent papers DIRECTLY (year-filtered), bypassing leaf membership.

    The topic tree was built on the pre-delta corpus, so the newest papers (e.g. 2026) have
    no leaf and the leaf-restricted recency inject can never reach them. This queries the
    embedding index for the `probe` nearest papers, keeps those >= frontier_year, and picks
    `want` newest-cohort-first — so leaf-less frontier work still enters the pool.
    """
    nodes = store.vector_pool_recent(qvec, frontier_year, probe)
    picked = frontier_select(nodes, frontier_year, want)
    return {n.arxiv_id: n for n in picked}


def refined_pool(
    store: Store,
    qvec: list[float],
    base_pool: dict[str, PoolNode],
    tree: TopicTree,
    min_year: int,
    target: int = 280,
    recent_k: int = 50,
    member_cap: int = 5000,
) -> tuple[dict[str, PoolNode], str | None, dict[str, int]]:
    """Leaf-replace anchor + citation-aware drill + recency inject. Returns (pool, leaf, stats).

    `min_year` is the topic-adaptive frontier cutoff (from recency.detect_frontier).
    """
    seeds = [(a, base_pool[a].score) for a in base_pool]
    leaf, path = dominant_leaf(tree, seeds)
    keep = anchor_keep(tree, list(base_pool), leaf, path, use_siblings=True)
    pool = {k: v for k, v in base_pool.items() if k in keep}
    n_anchor = len(pool)
    members = tree.members(leaf, limit=member_cap) if leaf else []
    drilled = citation_aware_drill(store, qvec, set(pool), members, target)
    pool.update(drilled)
    recent = recency_inject(store, qvec, set(pool), members, recent_k, min_year)
    pool.update(recent)
    stats = {
        "anchor": n_anchor,
        "drill": len(drilled),
        "recent": len(recent),
        "total": len(pool),
    }
    return pool, leaf, stats
