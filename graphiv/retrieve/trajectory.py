"""
Magnet-pulled trajectory selection, shipped as a quota on top of PPR

Walks branch toward reachable magnet mass, and decay fans successive lineages across facets
The ensemble is a fixed seed set because one walk is high-variance and a greedy one under-explores
"""

from __future__ import annotations

import random
from collections import Counter, deque

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.pagerank import personalized_pagerank, rank_landmarks_ppr

QUOTA = 8
SEEDS = 10
GAMMA = 0.4
MAX_LINEAGES = 50

Adj = dict[str, list[str]]


def _adjacency(edges: list[Edge]) -> Adj:
    adj: Adj = {}
    for e in edges:
        if e.src != e.dst:
            adj.setdefault(e.dst, []).append(e.src)  # cited (ancestor) -> citing
    return adj


def _reachable_mass(adj: Adj, w: dict[str, float]) -> dict[str, float]:
    radj: Adj = {}
    for u, cs in adj.items():
        for c in cs:
            radj.setdefault(c, []).append(u)
    r: dict[str, float] = {}
    for src, ws in w.items():
        if ws <= 0:
            continue
        seen: set[str] = {src}
        dq: deque[str] = deque([src])
        while dq:
            v = dq.popleft()
            r[v] = r.get(v, 0.0) + ws
            for p in radj.get(v, ()):
                if p not in seen:
                    seen.add(p)
                    dq.append(p)
    return r


def _lineage(
    root: str,
    adj: Adj,
    w: dict[str, float],
    r: dict[str, float],
    rng: random.Random,
) -> tuple[list[tuple[str, str]], dict[str, float]]:
    visited, collected = {root}, dict[str, float]()
    edges: list[tuple[str, str]] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if w.get(n, 0.0) > 0:
            collected[n] = w[n]
        cps = [(c, r.get(c, 0.0)) for c in adj.get(n, ()) if r.get(c, 0.0) > 0]
        if not cps:
            continue
        keyed = sorted(((rng.random() ** (1.0 / wt), c) for c, wt in cps), reverse=True)
        for _, c in keyed[:1]:  # k=1 linear threads (measured; decay covers facets)
            edges.append((n, c))
            if c not in visited:
                visited.add(c)
                stack.append(c)
    return edges, collected


def _one_run(
    adj: Adj, w0: dict[str, float], budget: int, seed: int
) -> tuple[list[str], list[list[str]]]:
    rng = random.Random(seed)
    w = dict(w0)
    picked: list[str] = []
    threads: list[list[str]] = []
    for _ in range(MAX_LINEAGES):
        if len(picked) >= budget:
            break
        r = _reachable_mass(adj, w)
        cand = [n for n in r if r[n] > 0]
        if not cand:
            break
        root = max(cand, key=lambda n: r[n])
        ledges, collected = _lineage(root, adj, w, r, rng)
        if not collected:
            break
        threads.append([root] + [c for _, c in ledges])
        for a in sorted(collected, key=lambda x: -collected[x]):
            if a not in set(picked):
                picked.append(a)
            w[a] = w.get(a, 0.0) * GAMMA
    return picked, threads


def consensus_picks(
    edges: list[Edge],
    grades: dict[str, Grade],
    exclude: set[str],
    pool_ids: set[str],
    quota: int,
) -> tuple[list[str], list[list[str]]]:
    """
    Top-`quota` new papers by collection frequency across SEEDS runs, plus the

        union of thread chains (foundational -> frontier) for the story graph.
    """
    w0 = {
        a: (g.relevance + 2) / 4
        for a, g in grades.items()
        if g.relevance >= 2 and a in pool_ids and a not in exclude
    }
    if not w0 or quota <= 0:
        return [], []
    adj = _adjacency(edges)
    freq: Counter[str] = Counter()
    threads: list[list[str]] = []
    for seed in range(SEEDS):
        picked, th = _one_run(adj, w0, quota * 3, seed)
        freq.update(picked)
        threads.extend(th)
    ranked = sorted(freq, key=lambda a: (-freq[a], -w0.get(a, 0.0), a))
    return ranked[:quota], threads


def rank_landmarks_trajectory(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    recent_year: int,
    recent_floor: int,
    now_year: int,
    grades: dict[str, Grade],
    quota: int = QUOTA,
) -> list[Landmark]:
    """
    Shipped hybrid: PPR (with frontier reservation) fills m-quota, consensus

        trajectory picks fill the rest; PPR order backfills if magnets run short.
    """
    q = min(quota, max(0, m - 1))
    base = rank_landmarks_ppr(pool, edges, m - q, recent_year, recent_floor, now_year)
    base_ids = {lm.arxiv_id for lm in base}
    picks, _threads = consensus_picks(edges, grades, base_ids, set(pool), q)
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    chosen = base + [
        Landmark(
            arxiv_id=pool[a].arxiv_id,
            title=pool[a].title,
            year=pool[a].year,
            category=pool[a].category,
            score=pool[a].score,
            in_degree=indeg.get(a, 0),
        )
        for a in picks
        if a in pool
    ]
    if len(chosen) < m:
        have = {lm.arxiv_id for lm in chosen}
        rest = {a: n for a, n in pool.items() if a not in have}
        seed = {a: max(n.score, 0.0) for a, n in rest.items()}
        ppr = personalized_pagerank(list(rest), edges, seed)
        for a in sorted(rest, key=lambda x: ppr.get(x, 0.0), reverse=True):
            chosen.append(
                Landmark(
                    arxiv_id=rest[a].arxiv_id,
                    title=rest[a].title,
                    year=rest[a].year,
                    category=rest[a].category,
                    score=rest[a].score,
                    in_degree=indeg.get(a, 0),
                )
            )
            if len(chosen) >= m:
                break
    return chosen[:m]
