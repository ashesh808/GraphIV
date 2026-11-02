"""Deployment settings preserve legacy PostgreSQL while cloud startup stays honest."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.paths import RUNTIME_CONFIG
from src.core.runtime import runtime_config
from src.mcp import state
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

    def missing():
        raise BlobNotFoundError("private provider error")

    monkeypatch.setattr(state, "_snapshot", missing)
    state.prepare_runtime()
    status = state.runtime_status()
    assert status["ready"] is False
    assert "Corpus manifest or a referenced artifact has not been published" in status["reasons"]
    assert "private provider error" not in str(status)


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
