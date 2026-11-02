"""Corpus contracts on real SQLite/FAISS fixtures and a recorded PostgreSQL transport."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.core.schema import Query
from src.mcp.what_cites import what_cites
from src.miner import store
from src.report.ground import exist
from src.retrieve.cosine import CosineRetriever
from src.retrieve.expand import fetch_papers
from src.retrieve.people import Person, find, topics
from src.storage import postgres
from src.storage.corpus import open_corpus
from src.storage.postgres import PostgresCorpus
from src.storage.sqlite import SQLiteCorpus

SCHEMA = Path(__file__).resolve().parents[2] / "src" / "storage" / "schema.sql"
VECTORS = {
    "a": [2.0, 0.0],
    "b": [0.6, 0.8],
    "c": [0.0, 1.0],
    "future": [0.9, 0.1],
    "old": [-1.0, 0.0],
    "unembedded": [1.0, 0.0],
}


def vector_blob(values: list[float]) -> bytes:
    return np.asarray(values, dtype="<f4").tobytes()


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "metadata.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA.read_text())
        connection.execute("INSERT INTO corpus_metadata VALUES ('embedding_dimension', '2')")
        for arxiv_id, when, stage, authors in [
            ("a", "2020-01-01", 3, "Ada Lovelace, Bo Li, Dee Ray"),
            ("b", "2021-01-01", 4, "Ada Lovelace, Bo Li, Dee Ray"),
            ("c", "2022-01-01", 3, "Ada Lovelace, Xu Wu"),
            ("future", "2023-01-01", 3, "Cy Young"),
            ("old", "2018-01-01", 3, "Foundational Author"),
            ("unembedded", "2022-01-02", 2, "Ada Lovelace"),
        ]:
            connection.execute(
                "INSERT INTO papers(arxiv_id,stage,title,abstract,date,"
                "primary_category,authors,surnames,embed_full) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    arxiv_id,
                    stage,
                    f"Title {arxiv_id}",
                    f"Abstract {arxiv_id}",
                    when,
                    "cs.AI",
                    authors,
                    json.dumps([name.split()[-1] for name in authors.split(", ")]),
                    vector_blob(VECTORS[arxiv_id]),
                ),
            )
        connection.execute("INSERT INTO papers(arxiv_id,stage,title) VALUES ('nodate',0,'Draft')")
        connection.executemany(
            "INSERT INTO vector_ids VALUES (?,?)", enumerate(["a", "b", "c", "future", "old"])
        )
        citations = [
            (1, "b", "a", 1, "First occurrence", "extends", 0.9),
            (2, "b", "a", 1, "Second occurrence", "extends", 0.8),
            (3, "c", "a", 1, "A successor", "extends", 0.8),
            (4, "future", "a", 1, "Beyond the cap", "extends", 0.9),
            (5, "unembedded", "a", 1, "An unembedded citer", "extends", 0.9),
            (6, "c", "b", 0, "Not labeled yet", "background", 0.9),
            (7, "old", "a", 1, "Below the score floor", "extends", 0.1),
            (8, "c", "a", 1, "A low-confidence critique", "critiques", 0.4),
            (9, "c", None, 1, "Unresolved", "extends", 0.9),
            (10, "c", "old", 1, None, None, 0.9),
            (11, "b", "old", 1, "Comparison", "compares", 0.9),
            (12, "a", "old", 0, "An unlabeled reference", "background", 0.9),
        ]
        connection.executemany("INSERT INTO citations VALUES (?,?,?,?,?,?,?)", citations)
        connection.executemany(
            "INSERT INTO topic_tree VALUES (?,?,?,?,?)",
            [("a", 1, 0, 1, 2), ("b", 1, 0, 1, 2), ("c", 0, 0, 3, 4)],
        )
        connection.executemany(
            "INSERT INTO topic_names VALUES (?,?,?,?)",
            [(0, None, None, "Root"), (0, 1, None, "Parent"), (0, 1, 2, "Leaf")],
        )
    return path


@pytest.fixture
def corpus(database: Path) -> SQLiteCorpus:
    return SQLiteCorpus(database, embedding_dimension=2)


def write_index(database: Path, destination: Path) -> None:
    faiss = pytest.importorskip("faiss")
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT p.embed_full FROM vector_ids v JOIN papers p ON p.arxiv_id=v.arxiv_id "
            "ORDER BY v.faiss_id"
        ).fetchall()
    vectors = np.stack([np.frombuffer(row[0], dtype="<f4") for row in rows]).astype("float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(destination))


def test_exact_and_faiss_seed_search_preserve_date_stage_and_blocked_filters(
    database: Path, corpus: SQLiteCorpus, tmp_path: Path
) -> None:
    index = tmp_path / "index.faiss"
    write_index(database, index)
    indexed = SQLiteCorpus(database, index, embedding_dimension=2)
    for backend in (corpus, indexed):
        rows = backend.search([1.0, 0.0], date(2022, 1, 1), ["a"], 2)
        assert [row[0] for row in rows] == ["b", "c"]
        assert [row[4] for row in rows] == pytest.approx([0.6, 0.0], abs=1e-6)
        assert backend.search([1.0, 0.0], date(2010, 1, 1), [], 10) == []
        papers = CosineRetriever(backend, blocked=["a"]).retrieve(
            Query(text="topic", emb=[1.0, 0.0], max_date=date(2022, 1, 1)), 2
        )
        assert [paper.arxiv_id for paper in papers] == ["b", "c"]


def test_faiss_filtering_widens_the_candidate_read_instead_of_shortening_the_pool(
    tmp_path: Path,
) -> None:
    database = tmp_path / "metadata.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA.read_text())
        for index in range(80):
            angle = (index + 1) / 90
            connection.execute(
                "INSERT INTO papers(arxiv_id,stage,title,abstract,date,embed_full) "
                "VALUES (?,3,?,?,?,?)",
                (
                    f"p{index}",
                    str(index),
                    "",
                    "2030-01-01" if index < 70 else "2020-01-01",
                    vector_blob([float(np.cos(angle)), float(np.sin(angle))]),
                ),
            )
            connection.execute("INSERT INTO vector_ids VALUES (?,?)", (index, f"p{index}"))
    path = tmp_path / "index.faiss"
    write_index(database, path)
    corpus = SQLiteCorpus(database, path)
    assert [row[0] for row in corpus.search([1.0, 0.0], date(2020, 1, 1), ["p70"], 3)] == [
        "p71",
        "p72",
        "p73",
    ]


def test_vector_helpers_return_original_values_and_metadata_reads_include_all_stages(
    corpus: SQLiteCorpus,
) -> None:
    assert store.read_seed(corpus, "a")[1] == [2.0, 0.0]
    assert store.read_seed(corpus, "unembedded") is None
    assert store.read_vectors(corpus, ["a", "unembedded"]) == {"a": [2.0, 0.0]}
    assert store.read_cosines(corpus, [1.0, 0.0], ["a", "b"]) == pytest.approx({"a": 1, "b": 0.6})
    assert exist(corpus, ["unembedded", "nodate", "missing"]) == {"unembedded", "nodate"}
    assert corpus.paper_details(["nodate"])[0][3] is None
    record = store.read_records(corpus, ["a", "c", "unembedded"])
    assert record["a"]["topic"] == ["Root", "Parent", "Leaf"]
    assert record["a"]["topic_id"] == [0, 1, 2]
    assert record["c"]["topic"] == []  # the placement is not completed
    assert record["unembedded"]["date"] == "2022-01-02"


def test_expansion_reads_keep_the_original_cutoff_without_changing_paper_order(
    corpus: SQLiteCorpus,
) -> None:
    papers = fetch_papers(
        corpus, Query(text="topic", emb=[1.0, 0.0]), ["a", "future", "b"], date(2021, 1, 1)
    )
    assert [paper.arxiv_id for paper in papers] == ["a", "b"]
    assert all(paper.date <= date(2021, 1, 1) for paper in papers)


def test_citation_occurrences_and_unlabeled_reference_semantics_are_distinct(
    corpus: SQLiteCorpus,
) -> None:
    edges = store.read_edges(corpus, ["a", "b", "c", "old"])
    assert sum(edge.source == "b" and edge.target == "a" for edge in edges) == 2
    assert not any(edge.source == "c" and edge.target == "b" for edge in edges)
    assert any(
        edge.target == "old" and edge.intent == "background" and edge.sentence == ""
        for edge in edges
    )
    references = corpus.references(["a", "b", "c"])
    assert references.count(("b", "a")) == 1
    assert ("c", "b") in references and ("a", "old") in references
    assert all(target is not None for _, target in references)


def test_successors_preserve_score_intent_and_exclusive_inclusive_window(
    corpus: SQLiteCorpus,
) -> None:
    result = store.read_successors(
        corpus, [1.0, 0.0], ["a"], date(2021, 1, 1), date(2022, 1, 1), ("extends",), 0.6
    )
    assert list(result) == ["c"]
    assert result["c"][1] == {"a": "extends"}
    assert result["c"][2] == ["A successor"]


def test_citing_papers_keep_inclusive_floor_newest_first_and_do_not_gate_paper_stage(
    corpus: SQLiteCorpus,
) -> None:
    rows = corpus.citing_papers("a", ["extends"], 0.6, "2021-01-01", 10)
    assert [row[0] for row in rows] == ["future", "unembedded", "c", "b", "b"]
    assert len(corpus.citing_papers("a", ["extends"], 0.6, None, 1)) == 1
    handles = SimpleNamespace(dsn=corpus)
    result = json.loads(what_cites(handles, "a", since="2021-01-01", limit=2))
    assert [row["arxiv_id"] for row in result] == ["future", "unembedded"]


def test_author_and_topic_reads_keep_existing_disambiguation_behavior(corpus: SQLiteCorpus) -> None:
    assert {row[0] for row in corpus.author_candidates("Lovelace", "%ada lovelace%")} == {
        "a",
        "b",
        "c",
    }
    assert corpus.author_candidates("lovelace", "%Ada Lovelace%") == []
    found = find(corpus, Person("Ada Lovelace", ("a",)))
    assert found.candidates == 3
    assert found.kept == ["a", "b"]
    assert topics(corpus, ["a", "c", "b"]) == {(0, 1): ["a", "b"], (-1, -1): ["c"]}
    assert corpus.topic_names() == [(0, 1, "Parent")]


def test_snapshot_open_rejects_corrupt_dimensions_and_never_creates_a_missing_database(
    database: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Manifest embedding dimension"):
        SQLiteCorpus(database, embedding_dimension=3)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        SQLiteCorpus(missing)
    assert not missing.exists()
    corpus = SQLiteCorpus(database)
    with pytest.raises(ValueError, match="Query dimension"):
        corpus.search([1.0, 0.0, 0.0], None, [], 1)


def test_index_open_rejects_wrong_metric_dimension_and_label_mapping(
    database: Path, tmp_path: Path
) -> None:
    faiss = pytest.importorskip("faiss")
    path = tmp_path / "index.faiss"
    faiss.write_index(faiss.IndexFlatL2(2), str(path))
    with pytest.raises(ValueError, match="inner product"):
        SQLiteCorpus(database, path)
    faiss.write_index(faiss.IndexFlatIP(3), str(path))
    with pytest.raises(ValueError, match="dimension"):
        SQLiteCorpus(database, path)
    faiss.write_index(faiss.IndexFlatIP(2), str(path))
    with pytest.raises(ValueError, match="every FAISS ordinal"):
        SQLiteCorpus(database, path)


def test_postgres_dsn_wrapper_preserves_rows_parameters_and_vector_representation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        ("b", "Title b", "Abstract b", date(2021, 1, 1), 0.6),
        ("a", "Title a", "Abstract a", date(2020, 1, 1), 1.0),
    ]
    calls = []
    connections = []

    class Connection:
        def execute(self, query, parameters=()):
            calls.append((query, parameters))
            return self

        def fetchall(self):
            return rows

    def connect(dsn):
        connections.append(dsn)
        return contextlib.nullcontext(Connection())

    monkeypatch.setattr(postgres.psycopg, "connect", connect)
    source = open_corpus("host=existing-store dbname=graphiv")
    assert isinstance(source, PostgresCorpus)
    assert open_corpus(source) is source
    got = store.read_papers("host=existing-store dbname=graphiv", [1 / 3, 0], ["a", "b"])
    assert [paper.arxiv_id for paper in got] == ["b", "a"]
    assert connections == ["host=existing-store dbname=graphiv"]
    assert calls == [(postgres.PAPERS, ("[0.333333,0.000000]", ["a", "b"]))]
    calls.clear()
    source.search([1 / 3, 0], date(2021, 1, 1), ["blocked"], 7)
    assert [
        query.as_string() if hasattr(query, "as_string") else query for query, _ in calls[:3]
    ] == [
        "SET hnsw.ef_search = 1000",
        "SET hnsw.max_scan_tuples = 200000",
        "SET hnsw.iterative_scan = relaxed_order",
    ]
    assert calls[-1] == (
        postgres.SEARCH,
        (
            "[0.333333,0.000000]",
            date(2021, 1, 1),
            date(2021, 1, 1),
            ["blocked"],
            "[0.333333,0.000000]",
            7,
        ),
    )
