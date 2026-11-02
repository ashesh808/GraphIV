"""Opt-in real pgvector compatibility against an exported SQLite/FAISS snapshot."""

from __future__ import annotations

import os
import uuid
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from offline.index_build.build import build_snapshot, postgres_rows
from src.storage.postgres import PostgresCorpus
from src.storage.sqlite import SQLiteCorpus

pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parents[2]
DIMENSION = 768


def padded(first: float, second: float) -> list[float]:
    return [first, second] + [0.0] * (DIMENSION - 2)


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


@pytest.fixture
def backends(tmp_path: Path):
    dsn = os.environ.get("GRAPHIV_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set GRAPHIV_TEST_POSTGRES_DSN for a disposable local pgvector server")
    options = conninfo_to_dict(dsn)
    if options.get("host") not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("The compatibility fixture accepts only a loopback test PostgreSQL server")
    schema = "graphiv_qa_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema))
        )
        try:
            connection.execute((ROOT / "offline/papers_preprocess/schema.sql").read_text())
            connection.execute((ROOT / "offline/topic_tree_creation/schema.sql").read_text())
            papers = [
                ("a", 3, "2020-01-01", "Ada Lovelace, Bo Li", ["Lovelace", "Li"], padded(2, 0)),
                ("b", 4, "2021-01-01", "Ada Lovelace, Bo Li", ["Lovelace", "Li"], padded(.6, .8)),
                ("c", 3, "2022-01-01", "Ada Lovelace, Xu Wu", ["Lovelace", "Wu"], padded(0, 1)),
                ("future", 3, "2023-01-01", "Cy Young", ["Young"], padded(.9, .1)),
                ("old", 3, "2018-01-01", "Foundational Author", ["Author"], padded(-1, 0)),
                ("unembedded", 2, "2022-01-02", "Ada Lovelace", ["Lovelace"], padded(1, 0)),
                ("nodate", 0, None, None, [], None),
            ]
            for arxiv_id, stage, when, authors, surnames, vector in papers:
                connection.execute(
                    "INSERT INTO papers(arxiv_id,stage,title,abstract,date,authors,surnames,"
                    "embed_full,primary_category,latest_version,survey_probability) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s::halfvec,'cs.AI','v1',0.5)",
                    (
                        arxiv_id, stage, f"Title {arxiv_id}", f"Abstract {arxiv_id}", when,
                        authors, surnames, vector_literal(vector) if vector is not None else None,
                    ),
                )
            citations = [
                (1, "b", "a", 1, "First occurrence", "extends", .9),
                (2, "b", "a", 1, "Second occurrence", "extends", .8),
                (3, "c", "a", 1, "A successor", "extends", .8),
                (4, "future", "a", 1, "Beyond the cap", "extends", .9),
                (5, "unembedded", "a", 1, "An unembedded citer", "extends", .9),
                (6, "c", "b", 0, "Not labeled yet", "background", .9),
                (7, "old", "a", 1, "Below the score floor", "extends", .1),
                (8, "c", "a", 1, "Low-confidence critique", "critiques", .4),
                (9, "c", None, 1, "Unresolved", "extends", .9),
                (10, "c", "old", 1, None, None, .9),
                (11, "b", "old", 1, "Comparison", "compares", .9),
                (12, "a", "old", 0, "An unlabeled reference", "background", .9),
            ]
            for row in citations:
                connection.execute(
                    "INSERT INTO citations(citation_id,source_id,target_id,stage,sentence,"
                    "intent,intent_score) VALUES(%s,%s,%s,%s,%s,%s,%s)", row,
                )
            for arxiv_id, stage, level0, level1, level2 in [
                ("a", 1, 0, 1, 2), ("b", 1, 0, 1, 2), ("c", 0, 0, 3, 4),
            ]:
                connection.execute(
                    "INSERT INTO topic_tree(arxiv_id,stage,embed_umap,level_0,level_1,level_2) "
                    "VALUES(%s,%s,%s::vector,%s,%s,%s)",
                    (arxiv_id, stage, vector_literal([0.0] * 50), level0, level1, level2),
                )
            for row in [(0, None, None, "Root"), (0, 1, None, "Parent"), (0, 1, 2, "Leaf")]:
                connection.execute("INSERT INTO topic_names VALUES(%s,%s,%s,%s)", row)
            destination = tmp_path / "snapshot"
            with connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                build_snapshot(
                    postgres_rows(connection, "papers"), postgres_rows(connection, "citations"),
                    destination, snapshot_id="postgres-integration", embedding_model="fixture",
                    embedding_dimension=DIMENSION, topics=postgres_rows(connection, "topics"),
                    topic_names=postgres_rows(connection, "topic_names"),
                )
            postgres = PostgresCorpus(connection=connection)
            exact = SQLiteCorpus(destination / "metadata.sqlite", embedding_dimension=DIMENSION)
            indexed = SQLiteCorpus(
                destination / "metadata.sqlite", destination / "index.faiss",
                embedding_dimension=DIMENSION,
            )
            yield postgres, exact, indexed
        finally:
            connection.execute("SET search_path TO public")
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def assert_scored(actual, expected, score_index=-1):
    assert len(actual) == len(expected)
    for left, right in zip(actual, expected, strict=True):
        assert left[:score_index] == right[:score_index]
        assert left[score_index] == pytest.approx(right[score_index], abs=1e-3)


def test_real_pgvector_search_matches_exported_exact_and_faiss_filters(backends):
    postgres, exact, indexed = backends
    for query in (padded(1, 0), padded(.3456789, .9135791)):
        for cutoff, blocked, limit in [
            (None, [], 5), (date(2022, 1, 1), ["a"], 3),
            (date(2021, 1, 1), [], 2), (date(2010, 1, 1), [], 10),
        ]:
            expected = postgres.search(query, cutoff, blocked, limit)
            for backend in (exact, indexed):
                assert_scored(backend.search(query, cutoff, blocked, limit), expected)


def test_real_postgres_metadata_and_occurrence_semantics_match_snapshot(backends):
    postgres, exact, _ = backends
    ids = ["a", "b", "c", "future", "old", "unembedded", "nodate", "missing"]
    for method, args in [
        ("edges", (ids,)), ("references", (ids,)), ("records", (ids,)),
        ("topics", (ids,)), ("topic_names", ()), ("existing_ids", (ids,)),
        ("paper_details", (ids,)), ("abstract_authors", (ids,)),
        ("author_candidates", ("Lovelace", "%ada lovelace%")),
        ("author_candidates", ("lovelace", "%Ada Lovelace%")),
    ]:
        assert Counter(getattr(exact, method)(*args)) == Counter(
            getattr(postgres, method)(*args)
        ), method
    assert sum(row[:2] == ("b", "a") for row in exact.edges(ids)) == 2
    assert exact.references(ids).count(("b", "a")) == 1
    assert exact.seed("unembedded") is postgres.seed("unembedded") is None
    for arxiv_id in ("a", "b", "future"):
        left, right = exact.seed(arxiv_id), postgres.seed(arxiv_id)
        assert left[:4] == right[:4]
        np.testing.assert_allclose(left[4], right[4], atol=1e-7, rtol=0)
    left = dict(exact.vectors(ids))
    right = dict(postgres.vectors(ids))
    assert left.keys() == right.keys()
    for arxiv_id in left:
        np.testing.assert_allclose(left[arxiv_id], right[arxiv_id], atol=1e-7, rtol=0)


def test_real_postgres_cosines_successors_and_citing_dates_match_snapshot(backends):
    postgres, exact, _ = backends
    query = padded(.3456789, .9135791)
    ids = ["a", "b", "c", "future", "old", "unembedded"]
    for method, args in [
        ("cosines", (query, ids)), ("papers", (query, ids)),
        ("successors", (query, ["a"], date(2021, 1, 1), date(2022, 1, 1), ("extends",), .6)),
    ]:
        actual = sorted(getattr(exact, method)(*args), key=lambda row: str(row[:-1]))
        expected = sorted(getattr(postgres, method)(*args), key=lambda row: str(row[:-1]))
        assert_scored(actual, expected)
    for since, limit in [(None, 10), ("2021-01-01", 10), ("2022-01-01", 2)]:
        actual = exact.citing_papers("a", ["extends"], .6, since, limit)
        expected = postgres.citing_papers("a", ["extends"], .6, since, limit)
        assert [row[3] for row in actual] == [row[3] for row in expected]
        assert Counter(actual) == Counter(expected)
