"""Compressed candidates retain exact half-vector scores and historical eligibility."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from offline.index_build.benchmark import evaluate_index, exact_neighbors, validate_document_space
from offline.index_build.indexes import build_index
from src.storage.sqlite import SQLiteCorpus

SCHEMA = Path(__file__).resolve().parents[2] / "src" / "storage" / "schema.sql"


@pytest.fixture
def half_corpus(tmp_path: Path):
    faiss = pytest.importorskip("faiss")
    previous = faiss.omp_get_max_threads()
    faiss.omp_set_num_threads(1)
    database = tmp_path / "metadata.sqlite"
    rng = np.random.default_rng(14)
    vectors = rng.normal(size=(512, 16)).astype("float16")
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA.read_text())
        connection.executemany(
            "INSERT INTO corpus_metadata VALUES (?,?)",
            [("embedding_dimension", "16"), ("vector_dtype", "float16")],
        )
        for number, vector in enumerate(vectors):
            connection.execute(
                "INSERT INTO papers(arxiv_id,stage,title,abstract,date,embed_full) "
                "VALUES (?,3,?,'','2020-01-01',?)",
                (f"p{number:04d}", f"Paper {number}", vector.astype("<f2").tobytes()),
            )
            connection.execute("INSERT INTO vector_ids VALUES (?,?)", (number, f"p{number:04d}"))
        path = tmp_path / "index.faiss"
        metrics = build_index(
            connection, path, 16, index_kind="ivfsq8", nlist=8, nprobe=1, train_size=512
        )
    try:
        yield database, path, vectors.astype("float64"), metrics
    finally:
        faiss.omp_set_num_threads(previous)


def test_half_precision_metadata_keeps_original_values_and_rescores_sq8_candidates(half_corpus):
    database, path, vectors, metrics = half_corpus
    corpus = SQLiteCorpus(database, path, embedding_dimension=16)
    assert corpus.vector_dtype == "float16"
    assert corpus.seed("p0000")[4] == vectors[0].tolist()
    query = vectors[0].tolist()
    rows = corpus.search(query, None, [], 12)
    assert rows[0][0] == "p0000"
    for arxiv_id, _, _, _, score in rows:
        vector = vectors[int(arxiv_id[1:])]
        expected = float(
            np.dot(vectors[0], vector) / (np.linalg.norm(vectors[0]) * np.linalg.norm(vector))
        )
        assert score == pytest.approx(expected, abs=1e-12)
    assert metrics["kind"] == "ivfsq8"
    assert metrics["training_vectors"] == 512
    assert metrics["index_bytes"] < 512 * 16 * 4
    assert corpus.nprobe == 1


def test_sparse_historical_filter_does_not_lose_an_eligible_unprobed_paper(half_corpus):
    from datetime import date

    database, path, vectors, _ = half_corpus
    corpus = SQLiteCorpus(database, path)
    query = (vectors[0] / np.linalg.norm(vectors[0])).astype("float32").reshape(1, -1)
    _, nearest_cell = corpus._index.quantizer.search(query, 1)
    _, cells = corpus._index.quantizer.search(vectors.astype("float32"), 1)
    other = next(number for number, cell in enumerate(cells[:, 0]) if cell != nearest_cell[0, 0])
    identifier = f"p{other:04d}"
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE papers SET date='2010-01-01' WHERE arxiv_id=?", (identifier,))
    rows = corpus.search(vectors[0].tolist(), date(2011, 1, 1), [], 5)
    assert [row[0] for row in rows] == [identifier]
    assert corpus.search(vectors[0].tolist(), date(2011, 1, 1), [identifier], 5) == []
    assert corpus._index.nprobe == 1  # per-request widening does not mutate shared index state


def test_unknown_vector_encoding_is_rejected_before_any_index_read(half_corpus):
    database, path, _, _ = half_corpus
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE corpus_metadata SET value='int8' WHERE key='vector_dtype'")
    with pytest.raises(ValueError, match="vector_dtype"):
        SQLiteCorpus(database, path)


def test_actual_vector_quality_receipt_checks_recall_scores_and_filters(half_corpus):
    database, path, vectors, _ = half_corpus
    corpus = SQLiteCorpus(database, path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE papers SET date='2000-01-01' WHERE arxiv_id='p0037'")
    query = vectors[0].tolist()
    queries = [
        {"id": "unfiltered", "embedding": query},
        {"id": "historical", "embedding": query, "date_max": "2010-01-01"},
        {
            "id": "blocked-historical",
            "embedding": query,
            "date_max": "2010-01-01",
            "blocked": ["p0037"],
        },
    ]
    baseline = exact_neighbors(corpus, queries, 20, batch_size=31)
    manual = sorted(
        [
            (
                f"p{number:04d}",
                float(
                    np.dot(vectors[0], vector)
                    / (np.linalg.norm(vectors[0]) * np.linalg.norm(vector))
                ),
            )
            for number, vector in enumerate(vectors)
        ],
        key=lambda item: -item[1],
    )[:20]
    assert [row[0] for row in baseline[0]] == [row[0] for row in manual]
    assert [row[0] for row in baseline[1]] == ["p0037"]
    assert baseline[2] == []
    receipt = evaluate_index(corpus, queries, top_k=20, nprobes=[8], min_recall=0.98)
    configurations = {config["nprobe"]: config for config in receipt["configurations"]}
    assert configurations[8]["minimum_recall_at_k"] == 1
    assert configurations[8]["max_abs_score_error"] < 1e-12
    assert configurations[8]["passed"]
    assert not configurations[1]["passed"]
    # A better sweep result cannot pass the currently deployed configuration.
    assert not receipt["active_configuration_passed"]
    assert receipt["recommended_nprobe"] == 8
    assert receipt["peak_process_rss_bytes"] > 0
    assert corpus.nprobe == 1


def test_document_space_receipt_compares_selected_actual_metadata_vectors(half_corpus):
    database, path, vectors, _ = half_corpus
    corpus = SQLiteCorpus(database, path)

    class Encoder:
        model_id = "test-only-encoder"
        revision = "a" * 40
        code_revision = "b" * 40

        def __init__(self):
            self.calls = []

        def encode_document(self, title: str, abstract: str) -> list[float]:
            self.calls.append((title, abstract))
            return vectors[int(title.split()[1])].tolist()

    encoder = Encoder()
    result = validate_document_space(corpus, encoder, samples=16)
    assert result["sample_count"] == len(encoder.calls) == 16
    assert all(abstract == "" for _, abstract in encoder.calls)
    assert result["passed"]
    assert result["minimum_cosine"] == pytest.approx(1.0, abs=1e-12)
    assert result["input_format"] == "search_document: Title: <title>\nAbstract: <abstract>"
    assert result["max_tokens"] == 512
