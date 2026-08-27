"""
The retrieval contract: a query in, a ranked cohort plus the evidence behind it out

A retriever is three swappable stages, so a baseline and the production path are one type
Every stage reads the Query's clock, which is what freezes the corpus for an eval run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import FrontierSpec


@dataclass(frozen=True)
class Query:
    """
    One retrieval request, including the clock that decides what the corpus contains

    Args:
        text: the natural-language question.
        budget: how many papers to return.
        now: the run's clock, set to a survey's own month for an eval run.
        max_yymm: absolute YYYYMM above which a paper is hidden, or None for the whole corpus.
        exclude: arXiv ids blocklisted outright.
        seed: a paper injected at top similarity, which makes `text` optional.
    """

    text: str
    budget: int
    now: datetime
    max_yymm: int | None = None
    exclude: frozenset[str] = frozenset()
    seed: str | None = None


@dataclass(frozen=True)
class Pool:
    """
    The candidate set a selector chooses from, with the graph induced over it
    """

    nodes: dict[str, PoolNode]
    edges: list[Edge]
    fr: FrontierSpec
    leaf: str | None = None


@dataclass(frozen=True)
class Selection:
    """
    Everything a selector may read, and nothing it may write
    """

    pool: dict[str, PoolNode]
    edges: list[Edge]
    budget: int
    fr: FrontierSpec
    grades: dict[str, Grade]


@dataclass(frozen=True)
class Retrieved:
    """
    A ranked cohort plus the evidence used to reach it, so a run can be explained offline
    """

    papers: list[Landmark]
    pool: dict[str, PoolNode]
    edges: list[Edge]
    fr: FrontierSpec
    grades: dict[str, Grade] = field(default_factory=dict[str, Grade])
    leaf: str | None = None
    trace: dict[str, float] = field(default_factory=dict[str, float])


class PoolBuilder(Protocol):
    """
    Turns a query into a candidate set, optionally with a citation graph over it
    """

    name: str

    def build(self, q: Query) -> Pool:
        """
        Candidate set for `q`, capped and blocklisted by the query's own clock
        """
        ...


class Reader(Protocol):
    """
    Assigns a role and a relevance to candidates, or declines to
    """

    name: str

    def grade(self, q: Query, pool: Pool) -> dict[str, Grade]:
        """
        Verdict per candidate, keyed by arxiv id, empty when the reader declines
        """
        ...


class Selector(Protocol):
    """
    Spends the query's budget on the pool
    """

    name: str

    def select(self, sel: Selection) -> list[Landmark]:
        """
        Up to `sel.budget` landmarks, ranked best first
        """
        ...


class Retriever(Protocol):
    """
    A whole retrieval path, from question to ranked cohort
    """

    name: str

    def retrieve(self, q: Query) -> Retrieved:
        """
        Ranked cohort for `q`, with the pool and grades that produced it
        """
        ...
