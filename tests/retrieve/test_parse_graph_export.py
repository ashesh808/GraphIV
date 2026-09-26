"""
Checks the export reader against a graph whose every edge is written out in the fixture
"""

from __future__ import annotations

from datetime import date

import numpy as np

from src.core.parse_graph_export import GraphExport, gather_rows


def test_index_maps_every_id(graph: GraphExport) -> None:
    """
    Every fixture id resolves to its own row
    """
    assert graph.n_papers == 8
    assert [graph.index[f"p{i}"] for i in range(8)] == list(range(8))


def test_cited_papers_are_what_the_paper_cites(graph: GraphExport) -> None:
    """
    p0 cites p4 and p5, p3 cites p0 and p1, and p4 cites nothing
    """
    assert sorted(graph.get_cited_papers(0).tolist()) == [4, 5]
    assert sorted(graph.get_cited_papers(3).tolist()) == [0, 1]
    assert graph.get_cited_papers(4).tolist() == []


def test_citing_papers_are_the_reverse(graph: GraphExport) -> None:
    """
    p4 is cited by p0 and p1, p0 is cited by p3, and p7 is cited by nobody
    """
    assert sorted(graph.get_citing_papers(4).tolist()) == [0, 1]
    assert graph.get_citing_papers(0).tolist() == [3]
    assert graph.get_citing_papers(7).tolist() == []


def test_citation_counts_match_the_edge_list(graph: GraphExport) -> None:
    """
    Eight edges give in-degrees 1, 1, 0, 1, 2, 2, 1, 0
    """
    assert graph.get_citation_counts().tolist() == [1, 1, 0, 1, 2, 2, 1, 0]


def test_citation_counts_before_drop_a_later_citer(graph: GraphExport) -> None:
    """
    p3 is dated 2022, so capping at 2021 leaves p0 and p1 uncited
    """
    rows = np.arange(8, dtype=np.int32)
    cap = graph.get_day_number(date(2021, 6, 1))
    assert graph.get_citation_counts_before(rows, cap).tolist() == [0, 0, 0, 0, 2, 2, 1, 0]


def test_citation_counts_before_drop_a_blocked_citer(graph: GraphExport) -> None:
    """
    Blocking p0 takes one citer off p4 and off p5
    """
    rows = np.arange(8, dtype=np.int32)
    cap = graph.get_day_number(date(2030, 1, 1))
    counts = graph.get_citation_counts_before(rows, cap, blocked=np.array([0], np.int32))
    assert counts.tolist() == [1, 1, 0, 1, 1, 1, 1, 0]


def test_neighbors_backward_are_what_the_set_cites(graph: GraphExport) -> None:
    """
    p0 and p1 together cite p4 twice and p5 once, so p4 ranks first
    """
    rows = np.array([0, 1], np.int32)
    assert graph.get_neighbors(rows, forward=False, limit=10).tolist() == [4, 5]


def test_neighbors_forward_are_what_cites_the_set(graph: GraphExport) -> None:
    """
    Only p3 cites either of p0 and p1
    """
    rows = np.array([0, 1], np.int32)
    assert graph.get_neighbors(rows, forward=True, limit=10).tolist() == [3]


def test_neighbors_respect_the_limit(graph: GraphExport) -> None:
    """
    The most reached neighbor survives a limit of one
    """
    rows = np.array([0, 1], np.int32)
    assert graph.get_neighbors(rows, forward=False, limit=1).tolist() == [4]


def test_walk_one_step_carries_the_weight(graph: GraphExport) -> None:
    """
    A unit weight on p0 and p1 lands on what they cite, so p4 takes 2 and p5 takes 1

    The walk is one step out, so the weighted papers keep nothing of their own.
    """
    weights = np.zeros(8)
    weights[[0, 1]] = 1.0
    assert graph.walk_one_step(weights, forward=False).tolist() == [0, 0, 0, 0, 2, 1, 0, 0]
    assert graph.walk_one_step(weights, forward=True).tolist() == [0, 0, 0, 2, 0, 0, 0, 0]


def test_gather_rows_concatenates_runs(graph: GraphExport) -> None:
    """
    Two runs of the flat array come back end to end, and no rows give an empty array
    """
    values = np.arange(10, dtype=np.int32)
    start = np.array([0, 5], np.int32)
    count = np.array([2, 3], np.int32)
    assert gather_rows(values, start, count).tolist() == [0, 1, 5, 6, 7]
    assert gather_rows(values, np.zeros(0, np.int32), np.zeros(0, np.int32)).tolist() == []
