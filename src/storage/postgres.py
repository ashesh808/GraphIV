"""PostgreSQL corpus adapter retaining the original SQL and pgvector search settings."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any, LiteralString

import psycopg
from psycopg import sql

from src.storage.corpus import (
    CitingRow,
    DetailRow,
    EdgeRow,
    RecordRow,
    ScoredPaperRow,
    SeedRow,
    SuccessorRow,
    VectorRow,
)

EDGES = """
SELECT source_id, target_id, intent, sentence
FROM citations
WHERE stage = 1 AND source_id = ANY(%s) AND target_id = ANY(%s) AND target_id IS NOT NULL
"""

COSINES = """
SELECT arxiv_id, 1 - (embed_full <=> %s::halfvec)
FROM papers WHERE arxiv_id = ANY(%s) AND stage >= 3
"""

SUCCESSORS = """
SELECT c.source_id, c.target_id, c.intent, c.sentence, p.date, p.title, p.abstract,
       1 - (p.embed_full <=> %s::halfvec)
FROM citations c JOIN papers p ON p.arxiv_id = c.source_id
WHERE c.stage = 1 AND c.target_id = ANY(%s) AND c.intent = ANY(%s)
  AND c.intent_score >= %s AND p.date > %s AND p.date <= %s AND p.stage >= 3
"""

PAPERS = """
SELECT arxiv_id, title, abstract, date, 1 - (embed_full <=> %s::halfvec)
FROM papers WHERE arxiv_id = ANY(%s) AND stage >= 3
"""

SEED = """
SELECT arxiv_id, title, abstract, date, embed_full::vector::real[]
FROM papers WHERE arxiv_id = %s AND stage >= 3
"""

VECTORS = """
SELECT arxiv_id, embed_full::vector::real[] FROM papers WHERE arxiv_id = ANY(%s) AND stage >= 3
"""

RECORDS = """
SELECT p.arxiv_id, p.title, p.abstract, p.date, p.primary_category, p.authors,
       t.level_0, t.level_1, t.level_2, g.name, m.name, l.name
FROM papers p
LEFT JOIN topic_tree t ON t.arxiv_id = p.arxiv_id AND t.stage = 1
LEFT JOIN topic_names g ON g.level_0 = t.level_0 AND g.level_1 IS NULL
LEFT JOIN topic_names m ON m.level_0 = t.level_0 AND m.level_1 = t.level_1 AND m.level_2 IS NULL
LEFT JOIN topic_names l
  ON l.level_0 = t.level_0 AND l.level_1 = t.level_1 AND l.level_2 = t.level_2
WHERE p.arxiv_id = ANY(%s)
"""

SEARCH = """
SELECT arxiv_id, title, abstract, date, 1 - (embed_full <=> %s::halfvec)
FROM papers
WHERE stage >= 3 AND (%s::date IS NULL OR date <= %s) AND NOT (arxiv_id = ANY(%s))
ORDER BY embed_full <=> %s::halfvec LIMIT %s
"""

CANDIDATES = """
SELECT arxiv_id, authors FROM papers
WHERE %s = ANY(surnames) AND authors ILIKE %s AND stage >= 3
"""

REFERENCES = """
SELECT DISTINCT source_id, target_id FROM citations
WHERE source_id = ANY(%s) AND target_id IS NOT NULL
"""

TOPICS = (
    """SELECT arxiv_id, level_0, level_1 FROM topic_tree WHERE arxiv_id = ANY(%s) AND stage = 1"""
)

TOPIC_NAMES = """
SELECT level_0, level_1, name FROM topic_names WHERE level_2 IS NULL AND level_1 IS NOT NULL
"""

EXISTS = """SELECT arxiv_id FROM papers WHERE arxiv_id = ANY(%s)"""

CITING = """
SELECT c.source_id, c.intent, c.sentence, p.date, p.title
FROM citations c JOIN papers p ON p.arxiv_id = c.source_id
WHERE c.stage = 1 AND c.target_id = %s AND c.intent = ANY(%s) AND c.intent_score >= %s
  AND (%s::date IS NULL OR p.date >= %s)
ORDER BY p.date DESC LIMIT %s
"""

ABSTRACT_AUTHORS = """SELECT arxiv_id, abstract, authors FROM papers WHERE arxiv_id = ANY(%s)"""

DETAILS = """SELECT arxiv_id, title, abstract, date FROM papers WHERE arxiv_id = ANY(%s)"""

EF_SEARCH = 1000
MAX_SCAN_TUPLES = 200000


def vector_literal(vector: list[float]) -> str:
    """Keep the original six-decimal pgvector input representation."""
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


class PostgresCorpus:
    """A lightweight adapter opening one connection per corpus operation."""

    def __init__(self, dsn: str = "", *, connection: psycopg.Connection[Any] | None = None) -> None:
        """Accept a legacy DSN or borrow a caller-owned connection."""
        self.dsn = dsn
        self.connection = connection

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection[Any]]:
        if self.connection is not None:
            yield self.connection
        else:
            with psycopg.connect(self.dsn) as connection:
                yield connection

    def _rows(self, query: LiteralString, parameters: tuple[Any, ...] = ()) -> list[Any]:
        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def search(
        self, vector: list[float], cap: date | None, blocked: list[str], limit: int
    ) -> list[ScoredPaperRow]:
        """Execute the unchanged iterative pgvector HNSW seed search."""
        literal = vector_literal(vector)
        with self._connect() as connection:
            _ = connection.execute(sql.SQL("SET hnsw.ef_search = {}").format(EF_SEARCH))
            _ = connection.execute(sql.SQL("SET hnsw.max_scan_tuples = {}").format(MAX_SCAN_TUPLES))
            _ = connection.execute("SET hnsw.iterative_scan = relaxed_order")
            return connection.execute(
                SEARCH, (literal, cap, cap, blocked, literal, limit)
            ).fetchall()

    def edges(self, arxiv_ids: list[str]) -> list[EdgeRow]:
        """Read every labeled occurrence induced on the paper set."""
        return self._rows(EDGES, (arxiv_ids, arxiv_ids))

    def edge_records(
        self, arxiv_ids: list[str]
    ) -> list[tuple[str, str, str | None, str | None, float | None]]:
        """Read each labeled occurrence and its original classifier confidence."""
        return self._rows(
            "SELECT source_id,target_id,intent,sentence,intent_score FROM citations "
            "WHERE stage=1 AND source_id=ANY(%s) AND target_id=ANY(%s) "
            "AND target_id IS NOT NULL",
            (arxiv_ids, arxiv_ids),
        )

    def cosines(self, vector: list[float], arxiv_ids: list[str]) -> list[tuple[str, float]]:
        """Read the original halfvec cosine expressions."""
        return self._rows(COSINES, (vector_literal(vector), arxiv_ids))

    def papers(self, vector: list[float], arxiv_ids: list[str]) -> list[ScoredPaperRow]:
        """Read complete embedded paper rows without changing their database order."""
        return self._rows(PAPERS, (vector_literal(vector), arxiv_ids))

    def seed(self, arxiv_id: str) -> SeedRow | None:
        """Read the seed and original vector from one paper row."""
        with self._connect() as connection:
            return connection.execute(SEED, (arxiv_id,)).fetchone()

    def vectors(self, arxiv_ids: list[str]) -> list[VectorRow]:
        """Read vectors at the same stage threshold as the original helper."""
        return self._rows(VECTORS, (arxiv_ids,))

    def successors(
        self,
        vector: list[float],
        arxiv_ids: list[str],
        since: date,
        until: date,
        intents: tuple[str, ...],
        floor: float,
    ) -> list[SuccessorRow]:
        """Read successor occurrences in the unchanged exclusive/inclusive window."""
        return self._rows(
            SUCCESSORS, (vector_literal(vector), arxiv_ids, list(intents), floor, since, until)
        )

    def records(self, arxiv_ids: list[str]) -> list[RecordRow]:
        """Keep all topic joins and their original null behavior."""
        return self._rows(RECORDS, (arxiv_ids,))

    def author_candidates(self, surname: str, pattern: str) -> list[tuple[str, str | None]]:
        """Read the original exact-surname and ILIKE author candidates."""
        return self._rows(CANDIDATES, (surname, pattern))

    def references(self, arxiv_ids: list[str]) -> list[tuple[str, str]]:
        """Read distinct resolved references without restricting citation stage."""
        return self._rows(REFERENCES, (arxiv_ids,))

    def topics(self, arxiv_ids: list[str]) -> list[tuple[str, int, int]]:
        """Read completed parent-topic membership."""
        return self._rows(TOPICS, (arxiv_ids,))

    def topic_names(self) -> list[tuple[int, int, str]]:
        """Read parent-topic names without roots or leaves."""
        return self._rows(TOPIC_NAMES)

    def existing_ids(self, arxiv_ids: list[str]) -> list[tuple[str]]:
        """Read identifiers at any processing stage for citation grounding."""
        return self._rows(EXISTS, (arxiv_ids,))

    def paper_details(self, arxiv_ids: list[str]) -> list[DetailRow]:
        """Read the unchanged metadata-only paper details."""
        return self._rows(DETAILS, (arxiv_ids,))

    def abstract_authors(self, arxiv_ids: list[str]) -> list[tuple[str, str | None, str | None]]:
        """Read abstracts and authors for the recall tool."""
        return self._rows(ABSTRACT_AUTHORS, (arxiv_ids,))

    def citing_papers(
        self,
        arxiv_id: str,
        intents: list[str],
        floor: float,
        since: str | None,
        limit: int,
    ) -> list[CitingRow]:
        """Preserve occurrence multiplicity and date-descending ordering."""
        return self._rows(CITING, (arxiv_id, intents, floor, since, since, limit))
