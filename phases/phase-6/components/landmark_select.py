"""Landmark set-selection objectives — PPR's competitors (experiment 02-06).

The shipped selector is fused-seeded personalized PageRank + the frontier reservation. PPR
optimizes item-wise *importance* (SEO-style "best page"); a literature review needs a *set*
with coverage and reliability — 02-02/02-06 showed PPR's rich-get-richer both admits famous
noise and starves relevant-but-peripheral clusters (SimPO/KTO never selected). Every arm here
consumes the same inputs (pool with fused scores in `.score`, edges, frontier spec, pool
embeddings where needed) and returns the chosen arxiv_ids for the non-reserved budget; the
frontier reservation stays outside (settled policy, applied by the caller).

All CPU: numpy over <=2k pool embeddings.
"""

from __future__ import annotations

import numpy as np

from pagerank import personalized_pagerank
from subgraph import Edge, PoolNode


def unit_matrix(
    pool: dict[str, PoolNode], embs: dict[str, list[float]]
) -> tuple[list[str], np.ndarray]:
    """Ids with embeddings + row-normalized matrix (cosine via dot product)."""
    ids = [a for a in pool if a in embs]
    m = np.array([embs[a] for a in ids], dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return ids, m / norms


def select_fused_topk(pool: dict[str, PoolNode], m: int) -> list[str]:
    """Pure top-m by fused score — the 'does the graph help selection at all' ablation."""
    return [n.arxiv_id for n in sorted(pool.values(), key=lambda n: -n.score)[:m]]


def select_ppr(pool: dict[str, PoolNode], edges: list[Edge], m: int) -> list[str]:
    """The incumbent (fused-seeded PPR), without the frontier reservation."""
    seed = {a: max(n.score, 0.0) for a, n in pool.items()}
    ppr = personalized_pagerank(list(pool), edges, seed)
    return sorted(pool, key=lambda a: -ppr.get(a, 0.0))[:m]


def select_mmr(
    pool: dict[str, PoolNode],
    embs: dict[str, list[float]],
    m: int,
    lam: float = 0.7,
) -> list[str]:
    """Greedy maximal marginal relevance: lam*fused - (1-lam)*max-sim-to-chosen."""
    ids, mat = unit_matrix(pool, embs)
    if not ids:
        return select_fused_topk(pool, m)
    fused = np.array([pool[a].score for a in ids], dtype=np.float32)
    chosen: list[int] = []
    max_sim = np.zeros(len(ids), dtype=np.float32)
    for _ in range(min(m, len(ids))):
        score = lam * fused - (1.0 - lam) * max_sim
        if chosen:
            score[np.array(chosen)] = -np.inf
        pick = int(np.argmax(score))
        chosen.append(pick)
        max_sim = np.maximum(max_sim, mat @ mat[pick])
    return [ids[i] for i in chosen]


def select_facility(
    pool: dict[str, PoolNode],
    embs: dict[str, list[float]],
    m: int,
) -> list[str]:
    """Facility location: every pool paper wants a similar landmark, fused-weighted.

    Greedy max of sum_p fused(p) * max(sim(p, chosen)) — junk clusters earn ~nothing
    (fused already zeroes reader-rejected papers), while any relevance-carrying cluster
    demands a representative even at low citation centrality (the SimPO/KTO fix).
    """
    ids, mat = unit_matrix(pool, embs)
    if not ids:
        return select_fused_topk(pool, m)
    w = np.clip(np.array([pool[a].score for a in ids], dtype=np.float32), 0.0, None)
    sims = mat @ mat.T  # (n, n) — <=2k pool, fits easily
    cover = np.zeros(len(ids), dtype=np.float32)
    chosen: list[int] = []
    for _ in range(min(m, len(ids))):
        gain = (np.maximum(sims, cover) - cover) @ w
        if chosen:
            gain[np.array(chosen)] = -np.inf
        pick = int(np.argmax(gain))
        chosen.append(pick)
        cover = np.maximum(cover, sims[pick])
    return [ids[i] for i in chosen]


def select_ppr_facility(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    embs: dict[str, list[float]],
    m: int,
    ppr_frac: float = 0.8,
) -> list[str]:
    """Hybrid: PPR fills ppr_frac of the budget, facility-location covers the remainder
    (the frontier-reservation pattern generalized from years to semantic clusters)."""
    m_ppr = max(1, round(ppr_frac * m))
    first = select_ppr(pool, edges, m_ppr)
    taken = set(first)
    ids, mat = unit_matrix(pool, embs)
    if not ids:
        return (first + [a for a in select_fused_topk(pool, m) if a not in taken])[:m]
    w = np.clip(np.array([pool[a].score for a in ids], dtype=np.float32), 0.0, None)
    sims = mat @ mat.T
    idx = {a: i for i, a in enumerate(ids)}
    cover = np.zeros(len(ids), dtype=np.float32)
    for a in first:
        if a in idx:
            cover = np.maximum(cover, sims[idx[a]])
    chosen = list(first)
    banned = {idx[a] for a in first if a in idx}
    while len(chosen) < min(m, len(pool)):
        gain = (np.maximum(sims, cover) - cover) @ w
        if banned:
            gain[np.array(sorted(banned))] = -np.inf
        pick = int(np.argmax(gain))
        if gain[pick] == -np.inf:
            break
        banned.add(pick)
        if ids[pick] not in taken:
            chosen.append(ids[pick])
            taken.add(ids[pick])
        cover = np.maximum(cover, sims[pick])
    return chosen[:m]


def select_proportional(
    pool: dict[str, PoolNode],
    embs: dict[str, list[float]],
    m: int,
    papers_per_cluster: int = 8,
) -> list[str]:
    """Cluster-proportional committee: k-means the pool embeddings, slots proportional to
    each cluster's fused mass, fused-ranked within cluster (Method-of-Equal-Shares flavor).
    """
    ids, mat = unit_matrix(pool, embs)
    if not ids:
        return select_fused_topk(pool, m)
    k = max(2, min(m // 2, round(m / papers_per_cluster)))
    labels = kmeans_labels(mat, k)
    fused = np.array([pool[a].score for a in ids], dtype=np.float32)
    mass = np.array(
        [float(np.clip(fused[labels == c], 0, None).sum()) for c in range(k)]
    )
    total = mass.sum() or 1.0
    quota = np.maximum(0, np.round(m * mass / total)).astype(int)
    chosen: list[str] = []
    for c in np.argsort(-mass):
        members = [i for i in np.argsort(-fused) if labels[i] == c]
        chosen.extend(ids[i] for i in members[: quota[c]])
    if len(chosen) < m:  # rounding slack: global fused order
        rest = [a for a in select_fused_topk(pool, len(pool)) if a not in set(chosen)]
        chosen.extend(rest[: m - len(chosen)])
    return chosen[:m]


def kmeans_labels(
    mat: np.ndarray, k: int, iters: int = 25, seed: int = 0
) -> np.ndarray:
    """Small deterministic k-means on unit vectors (cosine ~ euclidean here)."""
    rng = np.random.default_rng(seed)
    centers = mat[rng.choice(len(mat), size=min(k, len(mat)), replace=False)].copy()
    labels = np.zeros(len(mat), dtype=int)
    for _ in range(iters):
        labels = np.argmax(mat @ centers.T, axis=1)
        for c in range(len(centers)):
            members = mat[labels == c]
            if len(members):
                v = members.mean(axis=0)
                n = np.linalg.norm(v)
                if n > 0:
                    centers[c] = v / n
    return labels


def pool_coverage(
    landmark_ids: list[str],
    pool: dict[str, PoolNode],
    embs: dict[str, list[float]],
    min_score: float = 0.0,
) -> float:
    """Mean over (score > min_score) pool papers of max cosine to any landmark — the
    set-coverage metric the selection arms compete on."""
    ids, mat = unit_matrix(pool, embs)
    if not ids:
        return 0.0
    keep = [i for i, a in enumerate(ids) if pool[a].score > min_score]
    lm_rows = [i for i, a in enumerate(ids) if a in set(landmark_ids)]
    if not keep or not lm_rows:
        return 0.0
    sims = mat[keep] @ mat[lm_rows].T
    return float(sims.max(axis=1).mean())
