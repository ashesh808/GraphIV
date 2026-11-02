"""Typed corpus reads shared by PostgreSQL and immutable local snapshots."""

from __future__ import annotations

from datetime import date
from typing import Protocol

type ScoredPaperRow = tuple[str, str | None, str | None, date, float]
type DetailRow = tuple[str, str | None, str | None, date | None]
type VectorRow = tuple[str, list[float]]
type SeedRow = tuple[str, str | None, str | None, date, list[float]]
type EdgeRow = tuple[str, str, str | None, str | None]
type SuccessorRow = tuple[str, str, str, str | None, date, str | None, str | None, float]
type RecordRow = tuple[
    str,
    str | None,
    str | None,
    date | None,
    str | None,
    str | None,
    int | None,
    int | None,
    int | None,
    str | None,
    str | None,
    str | None,
]
type CitingRow = tuple[str, str, str | None, date, str | None]


class CorpusStore(Protocol):
    """Read operations required by retrieval, mining, grounding and MCP tools.

    Vector-bearing reads include only papers at stage 3 or later. Metadata-only
    reads include all stages, matching the original PostgreSQL queries. Methods
    without an explicit ranking retain the backing store's row order.
    """

    def search(
        self, vector: list[float], cap: date | None, blocked: list[str], limit: int
    ) -> list[ScoredPaperRow]:
        """Return the closest eligible embedded papers, highest cosine first."""
        ...

    def edges(self, arxiv_ids: list[str]) -> list[EdgeRow]:
        """Read labeled citation occurrences induced on the named paper set."""
        ...

    def cosines(self, vector: list[float], arxiv_ids: list[str]) -> list[tuple[str, float]]:
        """Read each embedded paper's cosine against the supplied query."""
        ...

    def papers(self, vector: list[float], arxiv_ids: list[str]) -> list[ScoredPaperRow]:
        """Read complete ranking rows for the named embedded papers."""
        ...

    def seed(self, arxiv_id: str) -> SeedRow | None:
        """Read an embedded seed paper and its original stored vector."""
        ...

    def vectors(self, arxiv_ids: list[str]) -> list[VectorRow]:
        """Read the original stored vectors for named embedded papers."""
        ...

    def successors(
        self,
        vector: list[float],
        arxiv_ids: list[str],
        since: date,
        until: date,
        intents: tuple[str, ...],
        floor: float,
    ) -> list[SuccessorRow]:
        """Read scored citations to the set in the window (since, until]."""
        ...

    def records(self, arxiv_ids: list[str]) -> list[RecordRow]:
        """Read paper metadata and its labeled topic-tree path, at any stage."""
        ...

    def author_candidates(self, surname: str, pattern: str) -> list[tuple[str, str | None]]:
        """Match an exact indexed surname and an SQL ILIKE author pattern."""
        ...

    def references(self, arxiv_ids: list[str]) -> list[tuple[str, str]]:
        """Read distinct resolved references from the papers, at any citation stage."""
        ...

    def topics(self, arxiv_ids: list[str]) -> list[tuple[str, int, int]]:
        """Read parent-topic membership from completed topic-tree rows."""
        ...

    def topic_names(self) -> list[tuple[int, int, str]]:
        """Read names of parent topics, excluding roots and leaf topics."""
        ...

    def existing_ids(self, arxiv_ids: list[str]) -> list[tuple[str]]:
        """Read which identifiers exist, including papers not yet embedded."""
        ...

    def paper_details(self, arxiv_ids: list[str]) -> list[DetailRow]:
        """Read identifier, title, abstract and date without a stage restriction."""
        ...

    def abstract_authors(self, arxiv_ids: list[str]) -> list[tuple[str, str | None, str | None]]:
        """Read abstracts and authors without a stage restriction."""
        ...

    def citing_papers(
        self,
        arxiv_id: str,
        intents: list[str],
        floor: float,
        since: str | None,
        limit: int,
    ) -> list[CitingRow]:
        """Read labeled citing occurrences, newest first, with an inclusive date floor."""
        ...


type CorpusSource = str | CorpusStore


def open_corpus(source: CorpusSource) -> CorpusStore:
    """Resolve a legacy PostgreSQL DSN or return an already-open corpus adapter.

    Args:
        source: A libpq DSN or a corpus implementing the explicit read contract.

    Returns:
        A lightweight PostgreSQL adapter or the supplied corpus, unchanged.
    """
    if isinstance(source, str):
        from src.storage.postgres import PostgresCorpus

        return PostgresCorpus(source)
    return source
