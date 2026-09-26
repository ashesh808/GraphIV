"""
The two steps between a graph ranking and a set of papers worth reading

The gate holds a ranking to the area the caller named, and the blend folds the reader in
Reserving slots for recent work measured worse than judging it on the citations it had time for
"""

from __future__ import annotations

from datetime import date

from src.core.parse_graph_export import GraphExport
from src.core.schema import Grade, Paper
from src.miner.era import per_year

GRAPH = 0.65
RELEVANCE = 0.35


def gate(papers: list[Paper], cosines: dict[str, float], power: float) -> list[Paper]:
    """
    Multiplies each score by how close its paper sits to the area, normalized to the pool's best

    A paper the store could not measure keeps its score, so a missing cosine never deletes one.

    Args:
        papers: The ranking.
        cosines: Cosine against the area anchor per paper.
        power: The exponent, where zero turns the gate off.

    Returns:
        The reordered ranking.
    """
    if power <= 0.0 or not cosines:
        return papers
    top = max(cosines.values()) or 1.0
    out: list[Paper] = []
    for paper in papers:
        held = cosines.get(paper.arxiv_id)
        if held is None:
            out.append(paper)
            continue
        factor = (max(held, 0.0) / top) ** power
        out.append(paper.model_copy(update={"score": (paper.score or 0.0) * factor}))
    return sorted(out, key=lambda p: -(p.score or 0.0))


def percentile(values: dict[str, float], keys: list[str]) -> dict[str, float]:
    """
    Rank percentile of each key, so a citation rate and a grade meet on one scale

    Args:
        values: The quantity to rank.
        keys: Every key that takes part, whether it carries a value or not.

    Returns:
        One percentile per key, the largest value at one.
    """
    order = sorted(keys, key=lambda k: (-values.get(k, 0.0), k))
    last = max(1, len(order) - 1)
    return {k: 1.0 - i / last for i, k in enumerate(order)}


def blend(
    papers: list[Paper],
    grades: dict[str, Grade],
    graph: GraphExport,
    asked: date,
    graph_weight: float = GRAPH,
    relevance_weight: float = RELEVANCE,
) -> list[Paper]:
    """
    Ranks papers by citations per year against what the reader thought of them

    Args:
        papers: The papers to rank.
        grades: What the reader said, where an ungraded paper sits at the neutral relevance.
        graph: The citation graph export, which holds the counts.
        asked: The date the run is capped at.
        graph_weight: What the citation rate is worth.
        relevance_weight: What the reader is worth.

    Returns:
        The papers, best first, each carrying its blended score.
    """
    if not papers:
        return []
    keys = [p.arxiv_id for p in papers]
    counts = graph.get_citation_counts()
    rates = {
        p.arxiv_id: per_year(
            int(counts[graph.index[p.arxiv_id]]) if p.arxiv_id in graph.index else 0,
            p.date,
            asked,
        )
        for p in papers
    }
    ranked = percentile(rates, keys)
    out = [
        paper.model_copy(
            update={
                "score": graph_weight * ranked[paper.arxiv_id]
                + relevance_weight
                * (grades[paper.arxiv_id].factor if paper.arxiv_id in grades else 0.5)
            }
        )
        for paper in papers
    ]
    return sorted(out, key=lambda p: -(p.score or 0.0))
