"""B2' — refined topic-graph retrieval (per checkpoint decisions).

Replaces the coarse arXiv-group anchor with topic-LEAF membership (recovers
interdisciplinary papers the group filter drops), then strengthens the pool with two
leaf-sourced, structure-preserving additions:

  - citation-aware drill: only add leaf members that have a CITES edge to the current
    pool (fixes the 0-edge collapse + the off-topic-drill bug from naive similarity drill).
  - recency injection: add recent (>= min_year) leaf members scored by similarity, so the
    frontier becomes retrievable (W2 is a retrieval problem, not a ranking one).

All additions come from the home leaf, so they stay on-topic by construction.
"""

from __future__ import annotations

from typing import Any


from subgraph import PoolNode  # noqa: E402
from topic_anchor import TopicTree, anchor_keep, dominant_leaf  # noqa: E402


def _node(r: Any, sim: float) -> PoolNode:
    return PoolNode(
        arxiv_id=str(r["id"]),
        title=str(r["t"] or ""),
        year=int(r["y"]) if r["y"] is not None else None,
        category=str(r["c"]) if r["c"] is not None else None,
        score=float(sim),
    )


def citation_aware_drill(
    session: Any, qvec: list[float], pool_ids: set[str], members: list[str], target: int
) -> dict[str, PoolNode]:
    """Add leaf members that cite or are cited by the pool, scored by similarity."""
    if len(pool_ids) >= target:
        return {}
    cand = [m for m in members if m not in pool_ids]
    if not cand:
        return {}
    rows = session.run(
        "MATCH (a:Paper)-[:CITES]-(b:Paper) "
        "WHERE a.arxiv_id IN $cand AND b.arxiv_id IN $pool AND a.embedding IS NOT NULL "
        "WITH DISTINCT a RETURN a.arxiv_id AS id, a.title AS t, a.year AS y, "
        "a.primary_category AS c, a.embedding AS e",
        cand=cand,
        pool=list(pool_ids),
    )
    scored = [(_score(qvec, r["e"]), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    out: dict[str, PoolNode] = {}
    for sim, r in scored[: max(0, target - len(pool_ids))]:
        out[str(r["id"])] = _node(r, sim)
    return out


def recency_inject(
    session: Any,
    qvec: list[float],
    pool_ids: set[str],
    members: list[str],
    k: int,
    min_year: int = 2023,
) -> dict[str, PoolNode]:
    """Add the top-`k` recent (>= min_year) leaf members by similarity to the query."""
    cand = [m for m in members if m not in pool_ids]
    if not cand or k <= 0:
        return {}
    rows = session.run(
        "MATCH (p:Paper) WHERE p.arxiv_id IN $cand AND p.year >= $y "
        "AND p.embedding IS NOT NULL "
        "RETURN p.arxiv_id AS id, p.title AS t, p.year AS y, p.primary_category AS c, "
        "p.embedding AS e",
        cand=cand,
        y=min_year,
    )
    scored = [(_score(qvec, r["e"]), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    return {str(r["id"]): _node(r, sim) for sim, r in scored[:k]}


def _score(qvec: list[float], emb: Any) -> float:
    return sum(a * b for a, b in zip(qvec, emb)) if emb else -1.0


def refined_pool(
    session: Any,
    qvec: list[float],
    base_pool: dict[str, PoolNode],
    tree: TopicTree,
    target: int = 280,
    recent_k: int = 30,
    member_cap: int = 5000,
) -> tuple[dict[str, PoolNode], str | None, dict[str, int]]:
    """Leaf-replace anchor + citation-aware drill + recency inject. Returns (pool, leaf, stats)."""
    seeds = [(a, base_pool[a].score) for a in base_pool]
    leaf, path = dominant_leaf(tree, seeds)
    keep = anchor_keep(tree, list(base_pool), leaf, path, use_siblings=True)
    pool = {k: v for k, v in base_pool.items() if k in keep}
    n_anchor = len(pool)
    members = tree.members(leaf, limit=member_cap) if leaf else []
    drilled = citation_aware_drill(session, qvec, set(pool), members, target)
    pool.update(drilled)
    recent = recency_inject(session, qvec, set(pool), members, recent_k)
    pool.update(recent)
    stats = {
        "anchor": n_anchor,
        "drill": len(drilled),
        "recent": len(recent),
        "total": len(pool),
    }
    return pool, leaf, stats
