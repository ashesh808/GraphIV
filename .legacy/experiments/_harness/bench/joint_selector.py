"""
The joint selector exactly as the survey bench runs it

It scores rank-percentile citations-per-year fused with reader relevance
The last slots go to LeyLine, and no slots are reserved for recent work
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.pagerank import personalized_pagerank
from graphiv.retrieve.recency import FrontierSpec, age_norm_score, frontier_select
from graphiv.retrieve.trajectory import consensus_picks

RRF_K = 60


def in_degree(edges: list[Edge]) -> dict[str, int]:
    """
    In-degree of every node in the induced subgraph
    """
    d: dict[str, int] = {}
    for e in edges:
        d[e.dst] = d.get(e.dst, 0) + 1
    return d


def _order(scores: dict[str, float], ids: list[str]) -> list[str]:
    """
    Ids sorted by score, descending, ties broken by id so the order is deterministic
    """
    return sorted(ids, key=lambda a: (-scores.get(a, 0.0), a))


def rrf(orders: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """
    Reciprocal rank fusion of several full orderings over the same id set
    """
    out: dict[str, float] = {}
    for o in orders:
        for i, a in enumerate(o):
            out[a] = out.get(a, 0.0) + 1.0 / (k + i + 1)
    return out


def pct(scores: dict[str, float], ids: list[str]) -> dict[str, float]:
    """
    Rank percentile of each id, so two scores on different scales can be blended
    """
    o = _order(scores, ids)
    n = max(1, len(o) - 1)
    return {a: 1.0 - i / n for i, a in enumerate(o)}


def signals(
    pool: dict[str, PoolNode], edges: list[Edge], fr: FrontierSpec
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    """
    The three base signals every candidate is assembled from, plus raw in-degree
    """
    ids = list(pool)
    indeg = in_degree(edges)
    ppr = personalized_pagerank(ids, edges, {a: max(pool[a].score, 0.0) for a in ids})
    agen = {a: age_norm_score(indeg.get(a, 0), pool[a].year, fr.now_year) for a in ids}
    cos = {a: pool[a].score for a in ids}
    return ppr, agen, cos, indeg


def assemble(
    scores: dict[str, float],
    pool: dict[str, PoolNode],
    edges: list[Edge],
    grades: dict[str, Grade],
    fr: FrontierSpec,
    m: int,
    quota: int = 0,
    reserve: bool = True,
) -> list[Landmark]:
    """
    Frontier reservation, then fill by score, then hand the last `quota` slots to LeyLine
    """
    indeg = in_degree(edges)
    lms = {
        a: Landmark(n.arxiv_id, n.title, n.year, n.category, n.score, indeg.get(a, 0))
        for a, n in pool.items()
    }
    chosen: list[Landmark] = []
    if reserve and len(lms) > m:
        by_score = [
            Landmark(n.arxiv_id, n.title, n.year, n.category, scores.get(a, 0.0), indeg.get(a, 0))
            for a, n in pool.items()
        ]
        chosen = [
            lms[lm.arxiv_id] for lm in frontier_select(by_score, fr.frontier_year, fr.recent_floor)
        ]
    have = {lm.arxiv_id for lm in chosen}
    budget = m - min(quota, max(0, m - len(chosen) - 1))
    for a in _order(scores, list(pool)):
        if len(chosen) >= budget:
            break
        if a not in have:
            chosen.append(lms[a])
            have.add(a)
    if quota > 0 and len(chosen) < m:
        picks, _ = consensus_picks(edges, grades, have, set(pool), m - len(chosen))
        for a in picks:
            if a in lms and a not in have:
                chosen.append(lms[a])
                have.add(a)
    for a in _order(scores, list(pool)):
        if len(chosen) >= m:
            break
        if a not in have:
            chosen.append(lms[a])
            have.add(a)
    for lm in chosen:
        g = grades.get(lm.arxiv_id)
        if g is not None:
            lm.role, lm.relevance = g.role, g.relevance
    return chosen[:m]


def candidates(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    grades: dict[str, Grade],
    fr: FrontierSpec,
    m: int,
    qrels: dict[str, int],
) -> dict[str, list[Landmark]]:
    """
    Every joint candidate over one frozen pool, plus the in-pool oracle ceiling
    """
    ids = list(pool)
    ppr, agen, cos, indeg = signals(pool, edges, fr)
    o_ppr, o_agen, o_cos = _order(ppr, ids), _order(agen, ids), _order(cos, ids)
    o_ind = _order({a: float(indeg.get(a, 0)) for a in ids}, ids)
    p_ppr, p_agen = pct(ppr, ids), pct(agen, ids)
    out: dict[str, list[Landmark]] = {}

    def add(
        name: str, scores: dict[str, float], **kw: Any
    ) -> None:  # pyright: ignore[reportExplicitAny]
        out[name] = assemble(scores, pool, edges, grades, fr, m, **kw)

    add("rrf_pf", rrf([o_ppr, o_agen]))
    add("rrf_pfc", rrf([o_ppr, o_agen, o_cos]))
    add("rrf_pfi", rrf([o_ppr, o_agen, o_ind]))
    add("rrf_pf_nores", rrf([o_ppr, o_agen]), reserve=False)
    for k in (10, 30, 120):
        add(f"rrf_pf_k{k}", rrf([o_ppr, o_agen], k=k))
        add(f"rrf_pf_k{k}_ley8", rrf([o_ppr, o_agen], k=k), quota=8)
    # weighting a fusion by repeating an ordering is the standard RRF weight trick
    add("rrf_2p1f", rrf([o_ppr, o_ppr, o_agen]))
    add("rrf_1p2f", rrf([o_ppr, o_agen, o_agen]))
    add("rrf_1p2f_ley8", rrf([o_ppr, o_agen, o_agen]), quota=8)
    for a in (0.25, 0.5, 0.75):
        add(f"blend{a}", {i: a * p_ppr[i] + (1 - a) * p_agen[i] for i in ids})
    add("blend0.25_ley8", {i: 0.25 * p_ppr[i] + 0.75 * p_agen[i] for i in ids}, quota=8)
    for q in (4, 8, 16):
        add(f"rrf_pf_ley{q}", rrf([o_ppr, o_agen]), quota=q)
    add("agen_only", agen)
    add("ppr_only", ppr)
    for q in (4, 8, 16):
        add(f"agen_ley{q}", agen, quota=q)

    """
    Grade-forward arms: the failure census says every base leaves 65-146 rel=+2 papers
    in the pool unpicked, so these spend slots on that class directly.
    """
    rel = {a: float(grades[a].relevance) if a in grades else 0.0 for a in ids}
    add("agen_gradefirst", {i: rel[i] * 1000.0 + p_agen[i] for i in ids})
    add("agen_gradefirst_ley8", {i: rel[i] * 1000.0 + p_agen[i] for i in ids}, quota=8)
    add("rrf_pf_gradefirst", {i: rel[i] * 1000.0 + pct(rrf([o_ppr, o_agen]), ids)[i] for i in ids})
    for w in (0.15, 0.25, 0.35, 0.45, 0.55, 0.7, 0.85):
        add(f"agen_relw{w}", {i: (1 - w) * p_agen[i] + w * (rel[i] + 2) / 4 for i in ids})
        add(
            f"agen_relw{w}_ley8",
            {i: (1 - w) * p_agen[i] + w * (rel[i] + 2) / 4 for i in ids},
            quota=8,
        )
        add(
            f"rrf_relw{w}_ley8",
            {i: (1 - w) * pct(rrf([o_ppr, o_agen]), ids)[i] + w * (rel[i] + 2) / 4 for i in ids},
            quota=8,
        )
    for q in (0, 2, 4, 12, 20):
        add(
            f"agen_relw0.35_ley{q}",
            {i: 0.65 * p_agen[i] + 0.35 * (rel[i] + 2) / 4 for i in ids},
            quota=q,
        )
    for q in (0, 4, 8, 16):
        add(
            f"agen_relw0.35_ley{q}_nores",
            {i: 0.65 * p_agen[i] + 0.35 * (rel[i] + 2) / 4 for i in ids},
            quota=q,
            reserve=False,
        )
    add("agen_only_nores", agen, reserve=False)

    gold_in = [a for a in ids if a in qrels]
    gold_in.sort(key=lambda a: -qrels[a])
    ora = gold_in[:m]
    out["ORACLE"] = [
        Landmark(
            pool[a].arxiv_id,
            pool[a].title,
            pool[a].year,
            pool[a].category,
            pool[a].score,
            indeg.get(a, 0),
        )
        for a in ora
    ]
    return out


SELECTORS: dict[str, Callable[..., list[Landmark]]] = {}
