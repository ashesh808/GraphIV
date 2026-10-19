"""
Splitting a list of papers into areas, and the ranking recall_paper reads from

Vectors are hand built, so nothing here embeds anything or reaches an endpoint
"""

from __future__ import annotations

import math
from datetime import date

from src.core.schema import Paper
from src.mcp.identify_areas import OUTSIDE, merge
from src.mcp.recall_paper import interleave, picks_first
from src.miner.store import mean_vector

VECTORS = {"a": [1.0, 0.0], "b": [0.9, 0.1], "c": [0.0, 1.0], "d": [0.05, 1.0]}


def paper(arxiv_id: str) -> Paper:
    """
    A paper with nothing but an id

    Args:
        arxiv_id: The id.

    Returns:
        The paper.
    """
    return Paper(arxiv_id=arxiv_id, title=arxiv_id, abstract="", date=date(2025, 1, 1))


def test_the_mean_vector_has_unit_length():
    got = mean_vector([[3.0, 0.0], [0.0, 4.0]])
    assert math.isclose(math.sqrt(sum(x * x for x in got)), 1.0)


def test_no_vectors_have_no_mean():
    assert mean_vector([]) == []


def test_two_close_areas_merge():
    got = merge([{"area": "x", "arxiv_ids": ["a"]}, {"area": "y", "arxiv_ids": ["b"]}], VECTORS)
    assert len(got) == 1 and sorted(got[0]["arxiv_ids"]) == ["a", "b"]


def test_two_far_areas_stay_apart():
    got = merge([{"area": "x", "arxiv_ids": ["a"]}, {"area": "y", "arxiv_ids": ["c"]}], VECTORS)
    assert len(got) == 2


def test_the_outside_area_never_merges():
    areas = [{"area": "x", "arxiv_ids": ["c"]}, {"area": OUTSIDE, "arxiv_ids": ["d"]}]
    assert len(merge(areas, VECTORS)) == 2


def test_interleave_alternates_and_keeps_the_earlier_place():
    first = [paper("a"), paper("b"), paper("c")]
    second = [paper("x"), paper("a"), paper("y")]
    assert [p.arxiv_id for p in interleave(first, second)] == ["a", "x", "b", "c", "y"]


def test_picks_lead_and_no_paper_repeats():
    pool = [paper("a"), paper("b"), paper("c")]
    assert [p.arxiv_id for p in picks_first([paper("c"), paper("a")], pool)] == ["c", "a", "b"]
