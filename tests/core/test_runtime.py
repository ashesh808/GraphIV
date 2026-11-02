"""Deployment settings preserve legacy PostgreSQL while cloud startup stays honest."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.paths import RUNTIME_CONFIG
from src.core.runtime import runtime_config
from src.mcp import state
from src.storage.artifacts import ArtifactManifest, Snapshot
from src.storage.blobs import BlobNotFoundError


def test_local_postgres_defaults_and_explicit_dsn(monkeypatch):
    monkeypatch.delenv("GRAPHIV_RUNTIME", raising=False)
    monkeypatch.delenv("GRAPHIV_STORAGE_BACKEND", raising=False)
    local = runtime_config(RUNTIME_CONFIG)
    assert local["storage"]["BACKEND"] == "postgres"
    assert "dbname=arxivkg" in local["database"]["PG_DEST"]
    assert local["endpoints"]["LLM_API"] == "http://localhost:11434/v1"
    monkeypatch.setenv("GRAPHIV_POSTGRES_DSN", "postgresql://graphiv@db/research")
    assert runtime_config(RUNTIME_CONFIG)["database"]["PG_DEST"] == (
        "postgresql://graphiv@db/research"
    )


def test_azure_uses_writable_paths_and_independent_model_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setenv("GRAPHIV_CACHE_PATH", str(tmp_path))
    monkeypatch.setenv("GRAPHIV_LLM_API_KEY", "llm-only")
    monkeypatch.delenv("GRAPHIV_EMBED_API_KEY", raising=False)
    config = runtime_config(RUNTIME_CONFIG)
    assert config["storage"]["BACKEND"] == "azure"
    assert not config["database"]["PG_DEST"]
    assert not config["endpoints"]["LLM_API"]
    assert not config["endpoints"]["EMBED_API"]
    assert config["endpoints"]["LLM_API_KEY"] == "llm-only"
    assert not config["endpoints"]["EMBED_API_KEY"]
    assert Path(config["serve"]["RUNS_PATH"]).is_relative_to(tmp_path)


def test_readiness_is_cheap_and_reports_missing_configuration(monkeypatch):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setattr(state, "_PREPARATION", {"complete": False, "reason": "Missing corpus"})
    monkeypatch.setattr(state, "_blob_service", lambda: pytest.fail("unexpected remote access"))
    result = state.runtime_status()
    assert result["ready"] is False
    assert result["storage"] == "azure"
    assert "Missing corpus" in result["reasons"]
    assert "Embedding endpoint is not configured" in result["reasons"]


def test_azure_corpus_selection_alone_initializes_cloud_paths(monkeypatch, tmp_path):
    monkeypatch.delenv("GRAPHIV_RUNTIME", raising=False)
    monkeypatch.setenv("GRAPHIV_STORAGE_BACKEND", "azure")
    monkeypatch.setenv("GRAPHIV_CACHE_PATH", str(tmp_path))
    config = runtime_config(RUNTIME_CONFIG)
    assert Path(config["storage"]["CACHE_PATH"]).is_relative_to(tmp_path)
    assert config["storage"]["REPORT_BACKEND"] == "azure"
    assert not config["endpoints"]["EMBED_API"]


def test_postgres_corpus_can_use_blob_reports_in_azure(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setenv("GRAPHIV_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("GRAPHIV_POSTGRES_DSN", "postgresql://graphiv@db/research")
    monkeypatch.setenv("GRAPHIV_GRAPH_PATH", str(tmp_path / "graph.npz"))
    config = runtime_config(RUNTIME_CONFIG)
    assert config["storage"]["BACKEND"] == "postgres"
    assert config["storage"]["REPORT_BACKEND"] == "azure"
    assert config["dataset"]["GRAPH_PATH"] == str(tmp_path / "graph.npz")


def test_missing_manifest_does_not_crash_http_preparation(monkeypatch):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setattr(state, "report_store", lambda: object())
    monkeypatch.setattr(state, "_PREPARATION", {"complete": False, "reason": ""})

    def missing(config_path):
        assert config_path == state.CONFIG
        raise BlobNotFoundError("private provider error")

    monkeypatch.setattr(state, "_snapshot", missing)
    state.prepare_runtime()
    status = state.runtime_status()
    assert status["ready"] is False
    assert "Corpus manifest or a referenced artifact has not been published" in status["reasons"]
    assert "private provider error" not in str(status)


def test_preparation_and_load_share_one_verified_snapshot(monkeypatch, tmp_path):
    from src.storage import sqlite

    cached = (state._snapshot, state.load, state.serving)
    for function in cached:
        function.cache_clear()
    monkeypatch.setattr(state, "_PREPARATION", {"complete": False, "reason": ""})
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setenv("GRAPHIV_CACHE_PATH", str(tmp_path / "cache"))
    monkeypatch.setenv("GRAPHIV_LLM_API_URL", "https://llm.example/v1")
    monkeypatch.setenv("GRAPHIV_LLM_MODEL", "report-model")
    monkeypatch.setenv("GRAPHIV_EMBED_BACKEND", "remote")
    monkeypatch.setenv("GRAPHIV_EMBED_API_URL", "https://embed.example/v1")
    monkeypatch.setenv("GRAPHIV_EMBED_MODEL", "snapshot-model")
    monkeypatch.setenv("GRAPHIV_METADATA_CONTAINER", "metadata")
    monkeypatch.setenv("GRAPHIV_MANIFEST_BLOB", "manifest.json")
    service = object()
    corpus = object()
    reports = object()
    manifest = {"snapshot_id": "verified-corpus", "capabilities": {"citation_sentences": False}}
    snapshot = Snapshot(
        root=tmp_path,
        database=tmp_path / "metadata.sqlite",
        index=tmp_path / "index.faiss",
        graph=tmp_path / "graph.npz",
        embedding_dimension=768,
        embedding_model="snapshot-model",
        manifest=ArtifactManifest("verified-corpus", 768, "snapshot-model", {}, manifest),
    )
    verified = []
    opened = []
    graphs = []

    def verify_snapshot(*args):
        verified.append(args)
        return snapshot

    def open_corpus(*args, **kwargs):
        opened.append((args, kwargs))
        return corpus

    def open_graph(path):
        graphs.append(path)
        return SimpleNamespace(n_papers=2)

    monkeypatch.setattr(state, "_blob_service", lambda: service)
    monkeypatch.setattr(state, "load_snapshot", verify_snapshot)
    monkeypatch.setattr(state, "report_store", lambda *_args: reports)
    monkeypatch.setattr(state, "load_graph_export", open_graph)
    monkeypatch.setattr(state, "Gemma", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(sqlite, "SQLiteCorpus", open_corpus)
    try:
        state.prepare_runtime()
        handles = state.load()
        assert state.runtime_status()["ready"] is True
        assert verified == [
            (service, "metadata", "manifest.json", tmp_path / "cache" / "snapshots")
        ]
        assert state._snapshot.cache_info().misses == 1
        assert state._snapshot.cache_info().hits == 1
        assert opened == [
            ((snapshot.database, snapshot.index), {"embedding_dimension": 768})
        ]
        assert graphs == [str(snapshot.graph)]
        assert handles.dsn is corpus
        assert handles.report_store is reports
        assert handles.corpus_info is manifest
        assert handles.citation_sentences is False
    finally:
        for function in cached:
            function.cache_clear()


def test_preparation_failure_never_exposes_a_dsn_or_secret(monkeypatch):
    monkeypatch.setattr(state, "report_store", lambda: object())
    monkeypatch.setattr(state, "_PREPARATION", {"complete": False, "reason": ""})
    monkeypatch.setattr(state, "_configuration_reasons", lambda _: [])

    def broken():
        raise RuntimeError("password=do-not-expose")

    monkeypatch.setattr(state, "load", broken)
    state.prepare_runtime()
    assert state.runtime_status()["ready"] is False
    assert "do-not-expose" not in str(state.runtime_status())


def test_query_embedding_uses_its_own_credential(monkeypatch):
    seen = []
    monkeypatch.setattr(state, "embed", lambda *args, **kwargs: seen.append((args, kwargs)))
    handles = SimpleNamespace(
        endpoints={
            "EMBED_API": "https://embed.example/v1",
            "EMBED_NAME": "corpus-model",
            "EMBED_API_KEY": "embedding-only",
            "LLM_API_KEY": "llm-only",
        }
    )
    state.Handles.embed(handles, "question")
    assert seen == [
        (
            ("https://embed.example/v1", "corpus-model", "question"),
            {"api_key": "embedding-only"},
        )
    ]


def test_explicit_empty_query_prefix_reaches_the_embedding_client(monkeypatch):
    seen = []
    monkeypatch.setattr(state, "embed", lambda *args, **kwargs: seen.append(kwargs))
    handles = SimpleNamespace(
        endpoints={
            "EMBED_API": "https://ai-gateway.vercel.sh/v1",
            "EMBED_NAME": "openai/text-embedding-3-small",
            "EMBED_QUERY_PREFIX": "",
        }
    )
    state.Handles.embed(handles, "question")
    assert seen == [{"query_prefix": ""}]


def test_local_nomic_enforces_published_query_space_without_remote_embedding_endpoint(monkeypatch):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    monkeypatch.setenv("GRAPHIV_EMBED_BACKEND", "local_nomic")
    monkeypatch.setenv("GRAPHIV_EMBED_MODEL", "openai/text-embedding-3-small")
    monkeypatch.setenv("GRAPHIV_EMBED_QUERY_PREFIX", "")
    config = runtime_config(RUNTIME_CONFIG)
    assert config["endpoints"]["EMBED_NAME"] == "nomic-embed-text-v2-moe"
    assert config["endpoints"]["EMBED_QUERY_PREFIX"] == "search_query: "
    assert "Embedding endpoint is not configured" not in state._configuration_reasons(config)


def test_local_nomic_query_uses_encoder_without_calling_remote_embedding_service(monkeypatch):
    class Encoder:
        def embed(self, text):
            assert text == "question"
            return [0.25] * 768

    monkeypatch.setattr(state, "embed", lambda *_args, **_kwargs: pytest.fail("remote fallback"))
    handles = SimpleNamespace(query_encoder=Encoder())
    assert state.Handles.embed(handles, "question") == [0.25] * 768
