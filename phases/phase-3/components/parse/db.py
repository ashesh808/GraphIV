"""Postgres helpers for phase_3.parse.

Connection params come from env (or sensible local defaults).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import psycopg
from psycopg import sql

from ._common import BASE_PATH

DB_DSN: str = os.environ.get(
    "ARXIVKG_PG_DSN", "dbname=arxiv-citations host=/run/postgresql"
)

SCHEMA_PATH: Path = BASE_PATH / "metadata" / "citation_schema.sql"


def connect() -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(DB_DSN)


def ensure_schema(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    # schema text comes from disk so it's `str` not LiteralString; route it
    # through SQL() by composing a typed identifier-free template.
    body = SCHEMA_PATH.read_bytes()
    with conn.cursor() as cur:
        _ = cur.execute(body)
    conn.commit()


def ensure_indexes(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    stmts: tuple[sql.SQL, ...] = (
        sql.SQL(
            "CREATE INDEX IF NOT EXISTS citation_cited_idx ON citation(cited_id) WHERE cited_id IS NOT NULL"
        ),
        sql.SQL(
            "CREATE INDEX IF NOT EXISTS citation_intent_null_idx ON citation(citing_id, ordinal) WHERE intent IS NULL"
        ),
    )
    with conn.cursor() as cur:
        for s in stmts:
            _ = cur.execute(s)
    conn.commit()


def populate_paper_table(
    conn: psycopg.Connection[tuple[object, ...]],
    arxiv_ids: Iterable[str],
) -> dict[str, int]:
    """Bulk-insert arxiv_ids into paper, return arxiv_id -> id mapping."""
    cur = conn.cursor()
    _ = cur.execute(sql.SQL("SELECT COUNT(*) FROM paper"))
    row = cur.fetchone()
    existing: int = cast(int, row[0]) if row is not None else 0
    if existing == 0:
        ids = list(arxiv_ids)
        with cur.copy(sql.SQL("COPY paper (arxiv_id) FROM STDIN")) as cp:
            for aid in ids:
                cp.write_row((aid,))
        conn.commit()

    mapping: dict[str, int] = {}
    _ = cur.execute(sql.SQL("SELECT id, arxiv_id FROM paper"))
    rows: list[tuple[int, str]] = (
        cur.fetchall()
    )  # pyright: ignore[reportAssignmentType]
    for pid, aid in rows:
        mapping[aid] = pid
    return mapping


CITATION_COLS: tuple[str, ...] = (
    "citing_id",
    "ordinal",
    "bib_local_id",
    "cited_id",
    "method",
    "score",
    "section",
    "sentence",
    "paragraph",
    "raw_bib_text",
    "co_cited_bibs",
)

CitationRow = tuple[
    int,
    int,
    str,
    int | None,
    str,
    float | None,
    str | None,
    str | None,
    str | None,
    str | None,
    list[str] | None,
]


def copy_citations(
    conn: psycopg.Connection[tuple[object, ...]],
    rows: Iterable[CitationRow],
) -> int:
    """Bulk-COPY rows into citation. Returns count written."""
    n = 0
    cols = sql.SQL(", ").join(sql.Identifier(c) for c in CITATION_COLS)
    stmt = sql.SQL("COPY citation ({cols}) FROM STDIN").format(cols=cols)
    with conn.cursor().copy(stmt) as cp:
        for r in rows:
            cp.write_row(r)
            n += 1
    return n
