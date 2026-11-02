"""Real local snapshot construction, immutable publication, and runtime compatibility."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from offline.index_build.build import POSTGRES_READS, build_snapshot, jsonl_rows, main
from src.core.parse_graph_export import load_graph_export
from src.storage.artifacts import ARTIFACT_FILENAMES, parse_manifest
from src.storage.blobs import file_sha256
from src.storage.sqlite import SQLiteCorpus

PAPERS = [
    {
        "arxiv_id": "a",
        "title": "Paper a",
        "abstract": "A real-input fixture",
        "stage": 3,
        "date": "2020-01-01",
        "authors": "Ada Lovelace",
        "surnames": ["Lovelace"],
        "embedding": [2.0, 0.0],
    },
    {
        "arxiv_id": "b",
        "title": "Paper b",
        "stage": 4,
        "date": "2021-01-01",
        "embed_full": [0.0, 3.0],
        "survey_probability": 0.4,
    },
    {"arxiv_id": "c", "title": "Paper c", "date": "2022-01-01", "embedding": [1.0, 1.0]},
    {"arxiv_id": "draft", "title": "Unembedded input", "stage": 0},
]
CITATIONS = [
    {
        "source_id": "b",
        "target_id": "a",
        "stage": 1,
        "intent": "extends",
        "sentence": "First",
        "intent_score": 0.9,
    },
    {
        "source_id": "b",
        "target_id": "a",
        "stage": 1,
        "intent": "extends",
        "sentence": "Second",
        "intent_score": 0.9,
    },
    {"source_id": "c", "target_id": "a", "stage": 0},
    {"source_id": "c", "target_id": "outside", "stage": 1},
    {"source_id": "outside", "target_id": "a", "stage": 1},
    {"source_id": "c", "target_id": None},
]


@pytest.mark.parametrize("write_vfs", ["", "unix-dotfile"])
def test_builder_outputs_are_consumed_by_the_actual_runtime_loaders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_vfs: str
) -> None:
    monkeypatch.setenv("GRAPHIV_SQLITE_WRITE_VFS", write_vfs)
    destination = tmp_path / "snapshot"
    manifest_path = build_snapshot(
        iter(PAPERS),
        iter(CITATIONS),
        destination,
        snapshot_id="test-corpus-v1",
        embedding_model="fixture-model",
        topics=[{"arxiv_id": "a", "level_0": 1, "level_1": 2, "level_2": 3}],
        topic_names=[{"level_0": 1, "name": "Root"}],
    )
    manifest = parse_manifest(manifest_path.read_bytes())
    assert manifest.snapshot_id == "test-corpus-v1"
    assert manifest.embedding_dimension == 2
    assert manifest.embedding_model == "fixture-model"
    assert manifest.raw["counts"] == {
        "papers": 4,
        "embedded": 3,
        "edges": 2,
        "citations": 6,
        "topics": 1,
        "topic_names": 1,
    }
    for role, reference in manifest.artifacts.items():
        assert reference.sha256 == file_sha256(destination / ARTIFACT_FILENAMES[role])
        assert reference.blob == f"snapshots/test-corpus-v1/{ARTIFACT_FILENAMES[role]}"
    assert manifest.artifacts["metadata"].container == "metadata"
    corpus = SQLiteCorpus(
        destination / "metadata.sqlite", destination / "index.faiss", embedding_dimension=2
    )
    assert corpus.seed("a")[4] == [
        2.0,
        0.0,
    ]  # FAISS normalization did not replace raw metadata vectors
    rows = corpus.search([1.0, 0.0], date(2021, 1, 1), [], 2)
    assert [row[0] for row in rows] == ["a", "b"]
    assert [row[4] for row in rows] == pytest.approx([1, 0])
    assert corpus.author_candidates("Lovelace", "%Ada Lovelace%") == [("a", "Ada Lovelace")]
    assert len(corpus.edges(["a", "b", "c"])) == 2
    graph = load_graph_export(destination / "graph.npz")
    assert [value.decode() for value in graph.ids] == ["a", "b", "c", "draft"]
    assert [graph.ids[row].decode() for row in graph.get_citing_papers(graph.index["a"])] == [
        "b",
        "c",
    ]
    assert graph.get_citation_counts().tolist() == [2, 0, 0, 0]
    assert graph.level[graph.index["a"]].tolist() == [1, 2, 3]
    assert graph.level[graph.index["b"]].tolist() == [-1, -1, -1]
    assert graph.day[graph.index["draft"]] == -(1 << 30)
    assert graph.survey[graph.index["a"]] == -1
    with sqlite3.connect(destination / "metadata.sqlite") as connection:
        assert connection.execute("SELECT count(*) FROM citations").fetchone()[0] == len(CITATIONS)


@pytest.mark.parametrize(
    "papers",
    [
        [],
        [{"arxiv_id": "a", "stage": 3, "date": "2020-01-01"}],
        [{"arxiv_id": "a", "embedding": [0.0, 0.0], "date": "2020-01-01"}],
    ],
)
def test_invalid_or_missing_real_vectors_never_publish_a_snapshot(
    tmp_path: Path, papers: list
) -> None:
    destination = tmp_path / "snapshot"
    with pytest.raises(ValueError):
        build_snapshot(
            papers, [], destination, snapshot_id="invalid-input", embedding_model="fixture-model"
        )
    assert not destination.exists()
    assert not list(tmp_path.glob(".snapshot-*"))


def test_existing_immutable_snapshot_is_never_replaced(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "retained.txt"
    marker.write_text("Keep this existing snapshot")
    with pytest.raises(FileExistsError):
        build_snapshot(
            PAPERS,
            CITATIONS,
            destination,
            snapshot_id="new-version",
            embedding_model="fixture-model",
        )
    assert marker.read_text() == "Keep this existing snapshot"


def test_mixed_dimensions_fail_atomically(tmp_path: Path) -> None:
    papers = [*PAPERS[:1], {"arxiv_id": "bad", "embedding": [1, 2, 3], "date": "2021-01-01"}]
    destination = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="inconsistent embedding dimension"):
        build_snapshot(
            papers, [], destination, snapshot_id="bad-dimension", embedding_model="fixture-model"
        )
    assert not destination.exists()


def test_jsonl_reader_rejects_non_objects_with_the_original_line_number(tmp_path: Path) -> None:
    source = tmp_path / "papers.jsonl"
    source.write_text('\n{"arxiv_id":"a"}\n[]\n')
    records = jsonl_rows(source)
    assert next(records) == {"arxiv_id": "a"}
    with pytest.raises(ValueError, match="papers.jsonl line 3"):
        next(records)


def test_jsonl_cli_builds_a_loadable_snapshot_without_any_service_connection(
    tmp_path: Path,
) -> None:
    papers = tmp_path / "papers.jsonl"
    papers.write_text("\n".join(json.dumps(record) for record in PAPERS) + "\n")
    citations = tmp_path / "citations.jsonl"
    citations.write_text("\n".join(json.dumps(record) for record in CITATIONS) + "\n")
    destination = tmp_path / "cli-snapshot"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "offline.index_build.build",
            "--papers",
            str(papers),
            "--citations",
            str(citations),
            "--out",
            str(destination),
            "--snapshot-id",
            "cli-fixture",
            "--embedding-model",
            "fixture-model",
        ],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Built immutable snapshot:" in result.stdout
    manifest = parse_manifest((destination / "manifest.json").read_bytes())
    assert manifest.snapshot_id == "cli-fixture"
    assert SQLiteCorpus(destination / "metadata.sqlite", destination / "index.faiss").seed("a")[
        4
    ] == [2.0, 0.0]


def test_postgres_export_uses_one_read_only_snapshot_and_streams_original_vector_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from offline.index_build import build

    queries = []
    rows = {
        "papers": [
            dict(
                record,
                embed_full=record.get("embed_full", record.get("embedding")),
                stage=record.get("stage", 3 if "embedding" in record else 0),
            )
            for record in PAPERS
        ],
        "citations": [dict(record, stage=record.get("stage", 0)) for record in CITATIONS],
        "topics": [],
        "topic_names": [],
    }

    class Cursor:
        def __init__(self, table):
            self.table = table
            self.description = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, query):
            queries.append(query)
            keys = list(dict.fromkeys(key for record in rows[self.table] for key in record))
            self.description = [SimpleNamespace(name=key) for key in keys]
            self.values = [tuple(record.get(key) for key in keys) for record in rows[self.table]]

        def __iter__(self):
            return iter(self.values)

    class Connection:
        def execute(self, query):
            queries.append(query)

        def cursor(self, *, name):
            return Cursor(name.removeprefix("snapshot_"))

    monkeypatch.setattr(build.psycopg, "connect", lambda _: contextlib.nullcontext(Connection()))
    monkeypatch.setenv("GRAPHIV_POSTGRES_DSN", "host=local-test dbname=fixture")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build",
            "--postgres",
            "--out",
            str(tmp_path / "snapshot"),
            "--snapshot-id",
            "pg-export",
            "--embedding-model",
            "fixture-model",
        ],
    )
    main()
    assert queries[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert queries[1:] == list(POSTGRES_READS.values())
    assert "embed_full::vector::real[] AS embed_full" in queries[1]
    seed = SQLiteCorpus(tmp_path / "snapshot" / "metadata.sqlite").seed("a")
    assert seed[4] == [2.0, 0.0]
