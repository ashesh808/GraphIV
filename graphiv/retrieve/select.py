"""
Selectors: one shared assembler over a swappable score, a reservation and a quota

Every shipped ranker is that same three-stage shape, so only the score function differs
Measured in 02-04: eight smooth score rules span 18 papers while the signals span 97
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from graphiv.core.models import Landmark, PoolNode
from graphiv.retrieve.api import Selection
from graphiv.retrieve.grade import fused_score
from graphiv.retrieve.pagerank import personalized_pagerank
from graphiv.retrieve.recency import age_norm_score, frontier_select
from graphiv.retrieve.trajectory import consensus_picks

W_GRAPH = 0.65
LEYLINE_QUOTA = 8

ScoreFn = Callable[[Selection], dict[str, float]]


def in_degree(sel: Selection) -> dict[str, int]:
    """
    In-degree of every pool paper within the induced subgraph
    """
    d: dict[str, int] = {}
    for e in sel.edges:
        d[e.dst] = d.get(e.dst, 0) + 1
    return d


def percentile(scores: dict[str, float]) -> dict[str, float]:
    """
    Rank percentile, so a citation rate and a -2..2 grade meet on one scale
    """
    order = sorted(scores, key=lambda a: (-scores[a], a))
    n = max(1, len(order) - 1)
    return {a: 1.0 - i / n for i, a in enumerate(order)}


def relevance(sel: Selection) -> dict[str, float]:
    """
    Reader relevance normalised to [0,1], neutral where a paper was not graded
    """
    return {
        a: ((float(sel.grades[a].relevance) if a in sel.grades else 0.0) + 2) / 4 for a in sel.pool
    }


def score_indegree(sel: Selection) -> dict[str, float]:
    """
    Raw in-pool in-degree, the bare graph ablation
    """
    d = in_degree(sel)
    return {a: float(d.get(a, 0)) for a in sel.pool}


def score_citations_per_year(sel: Selection) -> dict[str, float]:
    """
    In-degree over paper age, so a fast-rising recent paper competes with an old hub
    """
    d = in_degree(sel)
    return {a: age_norm_score(d.get(a, 0), sel.pool[a].year, sel.fr.now_year) for a in sel.pool}


def score_ppr(sel: Selection) -> dict[str, float]:
    """
    Personalized PageRank seeded by each paper's own similarity
    """
    seed = {a: max(n.score, 0.0) for a, n in sel.pool.items()}
    return personalized_pagerank(list(sel.pool), sel.edges, seed)


def score_cosine(sel: Selection) -> dict[str, float]:
    """
    Similarity alone, the no-graph no-reader baseline
    """
    return {a: n.score for a, n in sel.pool.items()}


def score_joint(sel: Selection) -> dict[str, float]:
    """
    Citations per year blended with reader relevance, the measured best
    """
    g = percentile(score_citations_per_year(sel))
    r = relevance(sel)
    return {a: W_GRAPH * g[a] + (1 - W_GRAPH) * r[a] for a in sel.pool}


def _fused(sel: Selection) -> Selection:
    """
    The ranking view of a pool: rejected papers dropped, similarity scaled by the grade
    """
    if not sel.grades:
        return sel
    keep: dict[str, PoolNode] = {}
    for a, n in sel.pool.items():
        g = sel.grades.get(a)
        if g is not None and g.relevance <= -2:
            continue
        keep[a] = PoolNode(n.arxiv_id, n.title, n.year, n.category, fused_score(n.score, g))
    return Selection(keep, sel.edges, sel.budget, sel.fr, sel.grades)


@dataclass(frozen=True)
class Recipe:
    """
    A named selector: how to score, whether to reserve frontier slots, how big the tail is

        With `fuse`, a paper the reader rejected leaves the ranking and stays in the graph as
        a connector, and every remaining similarity is multiplied by its grade.
        `tiebreak` is a second key, which matters because most papers share an in-degree.
    """

    score: ScoreFn
    reserve: bool = False
    quota: int = 0
    fuse: bool = True
    tiebreak: ScoreFn | None = None


def assemble(sel: Selection, recipe: Recipe) -> list[Landmark]:
    """
    Reserve, fill by score, hand the tail to the consensus walk, then top up

    Args:
        sel: the pool, graph, budget, frontier spec and grades.
        recipe: the score function and the two structural flags.

    Returns:
        Up to `sel.budget` landmarks carrying their true similarity and reader verdict.
    """
    ranked = _fused(sel) if recipe.fuse else sel
    scores = recipe.score(ranked)
    second = recipe.tiebreak(ranked) if recipe.tiebreak is not None else {}
    deg = in_degree(sel)
    lms = {
        a: Landmark(n.arxiv_id, n.title, n.year, n.category, n.score, deg.get(a, 0))
        for a, n in sel.pool.items()
    }
    by_score = sorted(ranked.pool, key=lambda a: (-scores.get(a, 0.0), -second.get(a, 0.0), a))
    chosen: list[Landmark] = []
    if recipe.reserve and len(ranked.pool) > sel.budget:
        """
        The reservation ranks within each recent year by similarity, not by the primary
        score, since a frontier paper has close to no in-degree to rank on.
        """
        by_sim = [
            Landmark(n.arxiv_id, n.title, n.year, n.category, n.score, deg.get(a, 0))
            for a, n in ranked.pool.items()
        ]
        chosen = [
            lms[lm.arxiv_id]
            for lm in frontier_select(by_sim, sel.fr.frontier_year, sel.fr.recent_floor)
        ]
    have = {lm.arxiv_id for lm in chosen}
    budget = sel.budget - min(recipe.quota, max(0, sel.budget - len(chosen) - 1))
    for a in by_score:
        if len(chosen) >= budget:
            break
        if a not in have:
            chosen.append(lms[a])
            have.add(a)
    if recipe.quota > 0 and len(chosen) < sel.budget:
        picks, _ = consensus_picks(
            sel.edges, sel.grades, have, set(ranked.pool), sel.budget - len(chosen)
        )
        for a in picks:
            if a in lms and a not in have:
                chosen.append(lms[a])
                have.add(a)
    for a in by_score:
        if len(chosen) >= sel.budget:
            break
        if a not in have:
            chosen.append(lms[a])
            have.add(a)
    for lm in chosen:
        g = sel.grades.get(lm.arxiv_id)
        if g is not None:
            lm.role, lm.relevance = g.role, g.relevance
    return chosen[: sel.budget]


SELECTORS: dict[str, Recipe] = {
    "joint": Recipe(score_joint, quota=LEYLINE_QUOTA),
    "frontier": Recipe(score_citations_per_year, reserve=True, tiebreak=score_cosine),
    "ppr": Recipe(score_ppr, reserve=True, tiebreak=score_citations_per_year),
    "trajectory": Recipe(
        score_ppr, reserve=True, quota=LEYLINE_QUOTA, tiebreak=score_citations_per_year
    ),
    "indegree": Recipe(score_indegree, tiebreak=score_cosine),
    "topk": Recipe(score_cosine, fuse=False),
}


class NamedSelector:
    """
    A registry entry bound to a name, so a pipeline can be built from strings
    """

    def __init__(self, name: str, recipe: Recipe | None = None) -> None:
        if recipe is None and name not in SELECTORS:
            raise KeyError(f"unknown selector {name!r}, have {sorted(SELECTORS)}")
        self.name = name
        self.recipe = recipe if recipe is not None else SELECTORS[name]

    def select(self, sel: Selection) -> list[Landmark]:
        """
        Up to `sel.budget` landmarks under this entry's recipe
        """
        return assemble(sel, self.recipe)
