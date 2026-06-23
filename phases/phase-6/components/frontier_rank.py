"""B3 — frontier-aware landmark ranking.

The shipped `rank_landmarks` sorts purely by within-pool in-degree, so recent papers
(which have not accumulated citations) almost never become landmarks — worst in mature
fields (W2: scaling 8/80, topological-insulators 0/80 from 2023+). This ranks in-degree
*within era* and guarantees a recent-era quota, so the frontier is represented while the
foundational papers still dominate Origins.

Drop-in alternative to subgraph.rank_landmarks(pool, edges, m).
"""

from __future__ import annotations


from recency import age_norm_score, frontier_select  # noqa: E402
from subgraph import Edge, Landmark, PoolNode  # noqa: E402


def _in_degree(edges: list[Edge]) -> dict[str, int]:
    d: dict[str, int] = {}
    for e in edges:
        d[e.dst] = d.get(e.dst, 0) + 1
    return d


def rank_landmarks_frontier(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    recent_year: int,
    recent_floor: int,
    now_year: int,
) -> list[Landmark]:
    """Top-`m` landmarks that GUARANTEE frontier representation.

    Reserve up to `recent_floor` slots for papers with year >= `recent_year` (the
    topic-adaptive frontier cutoff, ranked by similarity since recent papers have ~0
    in-degree), then fill the rest by age-normalized in-degree (citations-per-year) so a
    fast-rising recent paper competes with an old hub instead of being crowded out. If
    there aren't `recent_floor` recent papers, the remainder just goes to the fill.
    """
    indeg = _in_degree(edges)
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
        lms.sort(
            key=lambda lm: (age_norm_score(lm.in_degree, lm.year, now_year), lm.score),
            reverse=True,
        )
        return lms[:m]

    # 1. reserve frontier slots, newest-cohort-first (so 2025 AND 2026 both surface)
    recent = frontier_select(lms, recent_year, recent_floor)
    chosen: list[Landmark] = list(recent)
    chosen_ids: set[str] = {lm.arxiv_id for lm in chosen}

    # 2. fill the rest by age-normalized in-degree (citations-per-year) so the foundational
    #    spine survives but recent papers are judged on merit-per-opportunity, not raw count
    rest = sorted(
        (lm for lm in lms if lm.arxiv_id not in chosen_ids),
        key=lambda lm: (age_norm_score(lm.in_degree, lm.year, now_year), lm.score),
        reverse=True,
    )
    for lm in rest:
        if len(chosen) >= m:
            break
        chosen.append(lm)
        chosen_ids.add(lm.arxiv_id)
    return chosen[:m]
