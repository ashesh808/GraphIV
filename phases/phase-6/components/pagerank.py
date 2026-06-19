"""Personalized-PageRank landmark ranking (HippoRAG / GNN-RAG idea).

Raw in-degree favors old hubs; PPR over the induced citation subgraph, teleporting back to
the query-similar pool nodes, ranks papers by *topic-personalized influence* instead. Edges
flow citing->cited, so foundational-yet-on-topic papers accumulate rank. Frontier reservation
(recent papers, low rank by construction) is preserved from frontier_rank.
"""

from __future__ import annotations


import numpy as np

from subgraph import Edge, Landmark, PoolNode  # noqa: E402


def personalized_pagerank(
    nodes: list[str],
    edges: list[Edge],
    seed: dict[str, float],
    alpha: float = 0.85,
    iters: int = 80,
) -> dict[str, float]:
    """PPR over citing->cited edges, teleporting to `seed` (query-similarity weights)."""
    n = len(nodes)
    if n == 0:
        return {}
    idx = {a: i for i, a in enumerate(nodes)}
    out: list[list[int]] = [[] for _ in range(n)]
    for e in edges:
        if e.src in idx and e.dst in idx and e.src != e.dst:
            out[idx[e.src]].append(idx[e.dst])
    outdeg = np.array([len(o) for o in out], dtype=float)
    p = np.array([max(seed.get(a, 0.0), 0.0) for a in nodes], dtype=float)
    p = p / p.sum() if p.sum() > 0 else np.full(n, 1.0 / n)
    r = p.copy()
    dangling = np.where(outdeg == 0)[0]
    for _ in range(iters):
        rnew = (1.0 - alpha) * p + alpha * float(r[dangling].sum()) * p
        contrib = np.zeros(n)
        for i in np.where(outdeg > 0)[0]:
            share = alpha * r[i] / outdeg[i]
            for j in out[i]:
                contrib[j] += share
        rnew += contrib
        if np.abs(rnew - r).sum() < 1e-9:
            r = rnew
            break
        r = rnew
    return {a: float(r[idx[a]]) for a in nodes}


def _in_degree(edges: list[Edge]) -> dict[str, int]:
    d: dict[str, int] = {}
    for e in edges:
        d[e.dst] = d.get(e.dst, 0) + 1
    return d


def rank_landmarks_ppr(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    recent_year: int = 2023,
    recent_floor: int = 18,
) -> list[Landmark]:
    """Top-`m` by PPR, with the frontier reservation kept (recent papers by similarity)."""
    indeg = _in_degree(edges)
    seed = {a: max(node.score, 0.0) for a, node in pool.items()}
    ppr = personalized_pagerank(list(pool), edges, seed)
    lms = [
        Landmark(
            arxiv_id=n.arxiv_id,
            title=n.title,
            year=n.year,
            category=n.category,
            score=n.score,
            in_degree=indeg.get(n.arxiv_id, 0),
        )
        for n in pool.values()
    ]
    if len(lms) <= m:
        lms.sort(key=lambda lm: ppr.get(lm.arxiv_id, 0.0), reverse=True)
        return lms[:m]
    recent = sorted(
        (lm for lm in lms if lm.year is not None and lm.year >= recent_year),
        key=lambda lm: lm.score,
        reverse=True,
    )[:recent_floor]
    chosen: list[Landmark] = list(recent)
    chosen_ids: set[str] = {lm.arxiv_id for lm in chosen}
    rest = sorted(
        (lm for lm in lms if lm.arxiv_id not in chosen_ids),
        key=lambda lm: ppr.get(lm.arxiv_id, 0.0),
        reverse=True,
    )
    for lm in rest:
        if len(chosen) >= m:
            break
        chosen.append(lm)
        chosen_ids.add(lm.arxiv_id)
    return chosen[:m]
