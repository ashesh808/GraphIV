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
    """Idempotently insert any new arxiv_ids into paper, return arxiv_id -> id mapping.

    Incremental: COPYs only arxiv_ids not already present, so a delta run (new papers added
    to the corpus) interns them too — otherwise new papers get no citing_id and their
    citations are silently dropped.
    """
    cur = conn.cursor()
    _ = cur.execute(sql.SQL("SELECT arxiv_id FROM paper"))
    existing_ids: set[str] = {
        cast(str, r[0]) for r in cur.fetchall()  # pyright: ignore[reportAny]
    }
    new_ids = [aid for aid in arxiv_ids if aid not in existing_ids]
    if new_ids:
        with cur.copy(sql.SQL("COPY paper (arxiv_id) FROM STDIN")) as cp:
            for aid in new_ids:
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
