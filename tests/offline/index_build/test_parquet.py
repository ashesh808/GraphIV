"""Published Parquet ingestion preserves vectors, occurrences, confidence and topic names."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from offline.index_build import graph, run_hf
from offline.index_build.build import build_snapshot
from offline.index_build.parquet import ParquetSource
from src.core.parse_graph_export import load_graph_export
from src.storage.blobs import file_sha256
from src.storage.sqlite import SQLiteCorpus


def published_fixture(root: Path) -> Path:
    for table in ("papers", "citations", "topics"):
        (root / table).mkdir(parents=True)
    papers = pa.table(
        {
            "arxiv_id": ["a", "b", "c"],
            "title": ["Paper A", "Paper B", "Paper C"],
            "abstract": ["First abstract", "Second abstract", "Third abstract"],
            "date": pa.array([date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1)]),
            "authors": ["Ada Reader", "Bo Reader", "Cy Author"],
            "surnames": [["Reader"], ["Reader"], ["Author"]],
            "embedding": pa.FixedSizeListArray.from_arrays(
                pa.array(np.asarray([[1, 0], [0.6, 0.8], [0, 1]], dtype=np.float16).ravel()), 2
            ),
        }
    )
    pq.write_table(papers.slice(0, 2), root / "papers/papers-00000.parquet")
    pq.write_table(papers.slice(2), root / "papers/papers-00001.parquet")
    pq.write_table(
        pa.table(
            {
                "source_id": ["b", "b", "c"],
                "target_id": ["a", "a", "a"],
                "intent": ["extends", "extends", "critiques"],
                "intent_score": pa.array([0.95, 0.8, 0.9], type=pa.float32()),
            }
        ),
        root / "citations/citations-00000.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "arxiv_id": ["a", "b", "c"],
                "level_0": [0, 0, None],
                "level_1": [1, 1, None],
                "level_2": [2, 2, None],
                "name_0": ["Root", "Root", None],
                "name_1": ["Parent", "Parent", None],
                "name_2": ["Leaf", "Leaf", None],
            }
        ),
        root / "topics/topics-00000.parquet",
    )
    files = [
        {
            "name": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(root.glob("*/*.parquet"))
    ]
    manifest = root / "source.json"
    manifest.write_text(
        json.dumps({"repository": "kkuroma/GraphIV", "revision": "a" * 40, "files": files})
    )
    return manifest


def test_arrow_batches_preserve_float16_vectors_and_all_citation_occurrences(tmp_path: Path):
    manifest = published_fixture(tmp_path / "source")
    source = ParquetSource(manifest.parent, source_manifest=manifest, batch_size=1)
    papers = list(source.paper_rows())
    assert papers[1]["embed_full"].dtype == np.float16
    np.testing.assert_array_equal(papers[1]["embed_full"], np.asarray([0.6, 0.8], dtype=np.float16))
    citations = list(source.citation_rows())
    assert [row["citation_id"] for row in citations] == [1, 2, 3]
    assert sum(row["source_id"] == "b" for row in citations) == 2
    assert all(row["stage"] == 1 and row["sentence"] is None for row in citations)
    assert citations[0]["intent_score"] == float(np.float32(0.95))
    topics = list(source.topic_rows())
    assert [row["stage"] for row in topics] == [1, 1, 0]
    assert list(source.topic_name_rows()) == [
        {"level_0": 0, "level_1": None, "level_2": None, "name": "Root"},
        {"level_0": 0, "level_1": 1, "level_2": None, "name": "Parent"},
        {"level_0": 0, "level_1": 1, "level_2": 2, "name": "Leaf"},
    ]
    source.verify_counts()
    assert source.commit == "a" * 40
    assert source.expected_rows == {"papers": 3, "citations": 3, "topics": 3}


def test_published_source_builds_runtime_snapshot_without_jsonl_or_jit(tmp_path: Path):
    source_manifest = published_fixture(tmp_path / "source")
    source = ParquetSource(source_manifest.parent, source_manifest=source_manifest, batch_size=1)
    destination = tmp_path / "snapshot"
    output = build_snapshot(
        source.paper_rows(),
        source.citation_rows(),
        destination,
        topics=source.topic_rows(),
        topic_names=source.topic_name_rows(),
        snapshot_id="parquet-test",
        embedding_model="nomic-embed-text-v2-moe",
        embedding_dimension=2,
        vector_dtype="float16",
        index_kind="ivfsq8",
        nlist=1,
        nprobe=1,
        train_size=3,
        provenance=source.provenance(),
        expected_counts=source.expected_rows,
        capabilities={
            "precomputed_intents": True,
            "intent_confidence": True,
            "citation_sentences": False,
        },
    )
    source.verify_counts()
    manifest = json.loads(output.read_text())
    assert manifest["counts"] == {
        "papers": 3,
        "embedded": 3,
        "edges": 2,
        "citations": 3,
        "topics": 3,
        "topic_names": 3,
    }
    assert manifest["quality"]["citation_sentence_rows"] == 0
    assert manifest["capabilities"]["citation_sentences"] is False
    assert manifest["source"]["commit"] == "a" * 40
    corpus = SQLiteCorpus(destination / "metadata.sqlite", destination / "index.faiss")
    assert (
        corpus.seed("b")[4] == np.asarray([0.6, 0.8], dtype=np.float16).astype(np.float32).tolist()
    )
    assert [row[0] for row in corpus.search([1, 0], None, [], 3)] == ["a", "b", "c"]
    assert corpus.topic_names() == [(0, 1, "Parent")]
    assert len(corpus.edges(["a", "b", "c"])) == 3
    assert all(row[3] is None for row in corpus.edges(["a", "b", "c"]))
    assert not list(destination.glob("*.jsonl"))


def test_source_manifest_rejects_missing_shards_and_size_or_digest_changes(tmp_path: Path):
    manifest_path = published_fixture(tmp_path / "source")
    manifest = json.loads(manifest_path.read_text())
    original = manifest_path.read_text()
    for field, value in [("size", 1), ("sha256", "0" * 64)]:
        manifest["files"][0][field] = value
        manifest_path.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="source file"):
            ParquetSource(manifest_path.parent, source_manifest=manifest_path)
        manifest = json.loads(original)
    manifest["files"].pop()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="complete source manifest"):
        ParquetSource(manifest_path.parent, source_manifest=manifest_path)


def test_partial_parquet_consumption_is_detected(tmp_path: Path):
    manifest = published_fixture(tmp_path / "source")
    source = ParquetSource(manifest.parent, source_manifest=manifest)
    next(source.paper_rows())
    with pytest.raises(ValueError, match="Decoded Parquet row counts"):
        source.verify_counts()


def test_graph_uses_sqlite_deduplication_and_bounded_csr_batches(tmp_path: Path, monkeypatch):
    database = tmp_path / "metadata.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            (Path(__file__).resolve().parents[3] / "src/storage/schema.sql").read_text()
        )
        connection.executemany(
            "INSERT INTO papers(arxiv_id,date) VALUES (?,?)",
            [("a", "2020-01-01"), ("b", "2021-01-01"), ("c", "2022-01-01")],
        )
        connection.executemany(
            "INSERT INTO citations(source_id,target_id) VALUES (?,?)",
            [("b", "a"), ("b", "a"), ("c", "a"), ("c", "outside"), ("outside", "a")],
        )
        monkeypatch.setattr(graph, "CHUNK", 1)
        monkeypatch.setattr(
            np, "unique", lambda *_args, **_kwargs: pytest.fail("No giant np.unique")
        )
        target = tmp_path / "graph.npz"
        assert graph.write_graph(connection, target) == 2
    exported = load_graph_export(target)
    assert exported.cites_ptr.tolist() == [0, 2, 2, 2]
    assert exported.cites_idx.tolist() == [1, 2]
    assert exported.refs_ptr.tolist() == [0, 0, 1, 2]
    assert exported.refs_idx.tolist() == [0, 0]
    assert not list(tmp_path.glob(".graph-arrays-*"))


def fake_hf_metadata(monkeypatch, manifest_path: Path, *, token: str | None = None):
    """Supply real fixture file hashes through the same SDK metadata boundary as HF."""
    import huggingface_hub

    manifest = json.loads(manifest_path.read_text())
    siblings = [
        SimpleNamespace(
            rfilename=item["name"], size=item["size"], lfs=SimpleNamespace(sha256=item["sha256"])
        )
        for item in manifest["files"]
    ]

    class Api:
        def __init__(self, **_kwargs):
            pass

        def dataset_info(self, repository, *, revision, files_metadata):
            assert repository == "kkuroma/GraphIV"
            assert revision == "GraphIV-2026-10-01"
            assert files_metadata is True
            return SimpleNamespace(sha="a" * 40, siblings=siblings)

    monkeypatch.setattr(huggingface_hub, "HfApi", Api)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: token)
    monkeypatch.setattr(
        huggingface_hub,
        "snapshot_download",
        lambda *_args, **_kwargs: pytest.fail("A complete local fixture must not download data"),
    )
    monkeypatch.setenv("SQLITE_TMPDIR", str(manifest_path.parent))


def test_release_workflow_builds_all_rows_and_reuses_verified_snapshot(
    tmp_path: Path, monkeypatch, capsys
):
    workdir = tmp_path / "work"
    manifest_path = published_fixture(workdir / "source" / ("a" * 40))
    fake_hf_metadata(monkeypatch, manifest_path, token="test-secret-never-print")
    options = {"nlist": 1, "nprobe": 1, "train_size": 3}
    report = run_hf.run_release(workdir, **options)
    assert report["status"] == "complete"
    assert report["counts"]["citations"] == 3
    assert report["counts"]["papers"] == 3
    assert report["source"]["rows"] == {"papers": 3, "citations": 3, "topics": 3}
    assert all("sha256" in file for file in report["source"]["files"])
    assert report["peak_rss_bytes"] > 0
    assert json.loads((workdir / "build-report.json").read_text())["status"] == "complete"

    monkeypatch.setattr(
        run_hf,
        "build_snapshot",
        lambda *_args, **_kwargs: pytest.fail("A verified built snapshot must not rebuild"),
    )
    sentinel = object()
    monkeypatch.setattr(run_hf, "blob_service_from_environment", lambda: sentinel)
    publications = []

    def publish(client, destination, **kwargs):
        assert client is sentinel
        assert destination.is_dir()
        publications.append(kwargs)
        return {"activated": kwargs["activate"]}

    monkeypatch.setattr(run_hf, "publish_snapshot", publish)
    reused = run_hf.run_release(workdir, publish=True, activate=True, **options)
    assert reused["publication"] == {"activated": True}
    assert publications[0]["activate"] is True
    assert "reuse-built-snapshot" in [event["event"] for event in reused["events"]]
    assert "test-secret-never-print" not in capsys.readouterr().out
    assert "test-secret-never-print" not in (workdir / "build-report.json").read_text()
    with pytest.raises(ValueError, match="build options differ"):
        run_hf.run_release(workdir, **{**options, "seed": 1})


def test_release_workflow_never_downloads_gated_data_without_authentication(
    tmp_path: Path, monkeypatch
):
    manifest_path = published_fixture(tmp_path / "metadata")
    fake_hf_metadata(monkeypatch, manifest_path)
    workdir = tmp_path / "work"
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        run_hf.run_release(workdir)
    report = json.loads((workdir / "build-report.json").read_text())
    assert report["status"] == "failed"
    assert report["error_type"] == "RuntimeError"
    assert not (workdir / "snapshots").exists()


def test_release_activation_requires_explicit_publication(tmp_path: Path):
    with pytest.raises(ValueError, match="requires --publish"):
        run_hf.run_release(tmp_path, activate=True)
