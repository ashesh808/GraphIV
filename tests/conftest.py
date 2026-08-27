"""
Fixtures building a tiny pool by hand, so the retrieval tests need no database

Six papers over four citation edges is enough to separate every shipped selector
"""

from __future__ import annotations

from datetime import datetime

import pytest

from graphiv.core.models import Edge, PoolNode
from graphiv.retrieve.api import Pool, Query, Selection
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import FrontierSpec


@pytest.fixture
def nodes() -> dict[str, PoolNode]:
    """
    Two old hubs, two mid-era papers and two frontier papers, similarity descending
    """
    rows = [
        ("old.1", 2015, 0.61),
        ("old.2", 2016, 0.60),
        ("mid.1", 2020, 0.59),
        ("mid.2", 2021, 0.58),
        ("new.1", 2025, 0.57),
        ("new.2", 2026, 0.56),
    ]
    return {a: PoolNode(a, f"paper {a}", y, "cs", s) for a, y, s in rows}


@pytest.fixture
def edges() -> list[Edge]:
    """
    Everything cites old.1, so it is the only high-in-degree node
    """
    return [
        Edge("mid.1", "old.1", "background"),
        Edge("mid.2", "old.1", "background"),
        Edge("new.1", "old.1", "background"),
        Edge("new.1", "mid.1", "method"),
    ]


@pytest.fixture
def grades() -> dict[str, Grade]:
    """
    The frontier papers grade highest, which is where the reader disagrees with the graph
    """
    return {
        "old.1": Grade("foundational", 0, "old hub"),
        "mid.1": Grade("core", 1, "central"),
        "new.1": Grade("frontier", 2, "leading edge"),
        "new.2": Grade("frontier", 2, "leading edge"),
    }


@pytest.fixture
def frontier() -> FrontierSpec:
    """
    Frontier starts at 2025 with two reserved slots
    """
    return FrontierSpec(frontier_year=2025, recent_floor=2, now_year=2026)


@pytest.fixture
def pool(nodes: dict[str, PoolNode], edges: list[Edge], frontier: FrontierSpec) -> Pool:
    """
    The fixture pool with its graph induced
    """
    return Pool(nodes, edges, frontier, leaf="test-leaf")


@pytest.fixture
def query() -> Query:
    """
    A four-slot request clocked at 2026-08
    """
    return Query(text="what is happening in this field", budget=4, now=datetime(2026, 8, 27))


@pytest.fixture
def selection(
    nodes: dict[str, PoolNode],
    edges: list[Edge],
    frontier: FrontierSpec,
    grades: dict[str, Grade],
) -> Selection:
    """
    A four-slot selection over the fixture pool
    """
    return Selection(nodes, edges, 4, frontier, grades)
