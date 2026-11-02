"""Authenticated corpus validation reads real adapter metadata without model work."""

import sqlite3
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from apps.api import server
from src.mcp.state import serving
from src.storage.runs import LocalReportStore
from src.storage.sqlite import SQLiteCorpus

ENDPOINT = "/api/corpus/validate"
SCHEMA = Path(__file__).resolve().parents[2] / "src" / "storage" / "schema.sql"


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    for name in ("GRAPHIV_API_TOKEN", "GRAPHIV_REQUIRE_AUTH", "GRAPHIV_RUNTIME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, "READONLY", False)
    monkeypatch.setattr("src.mcp.state.prepare_runtime", lambda: None)


def application(tmp_path, ready=True, role="both", status_callback=None):
    settings = replace(serving(), runs=tmp_path / "runs", pdfs=tmp_path / "pdfs")
    return server.build_http_app(
        settings,
        role=role,
        status_callback=status_callback
        or (lambda: {"ready": ready, "reasons": [] if ready else ["Corpus pending"]}),
        report_store=LocalReportStore(settings.runs),
    )


def forbid_load():
    pytest.fail("Rejected validation requests must not load or query the corpus")


def test_corpus_validation_returns_503_without_loading_an_unready_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load", forbid_load)
    with TestClient(application(tmp_path, ready=False)) as client:
        response = client.post(ENDPOINT, json={"ids": ["1706.03762"]})
        assert response.status_code == 503
        assert response.json() == {"error": "Research runtime is not ready"}
        assert client.get("/health/live").status_code == 200


def test_corpus_validation_requires_the_bearer_before_touching_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPHIV_API_TOKEN", "corpus-test-token")
    monkeypatch.setattr(server, "load", forbid_load)
    with TestClient(application(tmp_path)) as client:
        for headers in ({}, {"Authorization": "Bearer incorrect"}):
            response = client.post(ENDPOINT, json={"ids": ["1706.03762"]}, headers=headers)
            assert response.status_code == 401
            assert response.headers["WWW-Authenticate"] == "Bearer"
            assert "corpus-test-token" not in response.text


def test_corpus_validation_rejects_an_oversized_stream_before_adapter_access(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load", forbid_load)
    chunks = [b'{"ids":["1706.03762"],"padding":"', b"x" * 131072, b'"}']
    with TestClient(application(tmp_path)) as client:
        response = client.post(
            ENDPOINT, content=iter(chunks), headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
        assert response.json() == {"error": "Too many paper identifiers"}


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"ids": "1706.03762"},
        {"ids": []},
        {"ids": ["a"] * 1001},
        {"ids": [""]},
        {"ids": ["a" * 81]},
        {"ids": [17]},
        {"ids": [None]},
    ],
)
def test_corpus_validation_rejects_invalid_id_lists_before_adapter_access(
    tmp_path, monkeypatch, body
):
    monkeypatch.setattr(server, "load", forbid_load)
    with TestClient(application(tmp_path)) as client:
        response = client.post(ENDPOINT, json=body)
        assert response.status_code == 422
        assert response.json() == {"error": "Pass 1–1000 paper identifiers"}


@pytest.mark.parametrize("body", [b"not json", b'{"ids":["\xff"]}'])
def test_corpus_validation_rejects_malformed_json_and_utf8(tmp_path, monkeypatch, body):
    monkeypatch.setattr(server, "load", forbid_load)
    with TestClient(application(tmp_path)) as client:
        assert client.post(ENDPOINT, content=body).status_code == 422


def test_corpus_validation_returns_real_sqlite_metadata_and_missing_ids(tmp_path, monkeypatch):
    database = tmp_path / "metadata.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA.read_text())
        connection.executemany(
            "INSERT INTO papers(arxiv_id,stage,title,abstract,date,primary_category,authors) "
            "VALUES (?,?,?,?,?,?,?)",
            [
                (
                    "1706.03762",
                    3,
                    "Attention Is All You Need",
                    "A metadata fixture read through the production SQLite adapter.",
                    "2017-06-12",
                    "cs.CL",
                    "A. Author, B. Author",
                ),
                ("draft", 0, "Unembedded draft", None, None, None, None),
            ],
        )
    corpus = SQLiteCorpus(database)
    seen = []
    loop_threads = []
    original_records = corpus.records

    def records(ids):
        seen.append((ids, threading.get_ident()))
        return original_records(ids)

    def readiness():
        loop_threads.append(threading.get_ident())
        return {"ready": True, "reasons": []}

    monkeypatch.setattr(corpus, "records", records)
    monkeypatch.setattr(server, "load", lambda: SimpleNamespace(dsn=corpus))
    monkeypatch.setenv("GRAPHIV_API_TOKEN", "corpus-test-token")
    with TestClient(application(tmp_path, status_callback=readiness)) as client:
        response = client.post(
            ENDPOINT,
            json={"ids": ["missing-first", "draft", "1706.03762", "draft", "missing-last"]},
            headers={"Authorization": "Bearer corpus-test-token"},
        )
    assert response.status_code == 200
    result = response.json()
    papers = {paper["arxiv_id"]: paper for paper in result["papers"]}
    assert papers == {
        "1706.03762": {
            "arxiv_id": "1706.03762",
            "title": "Attention Is All You Need",
            "abstract": "A metadata fixture read through the production SQLite adapter.",
            "date": "2017-06-12",
            "primary_category": "cs.CL",
            "authors": "A. Author, B. Author",
        },
        "draft": {
            "arxiv_id": "draft",
            "title": "Unembedded draft",
            "abstract": None,
            "date": None,
            "primary_category": None,
            "authors": None,
        },
    }
    assert result["missing"] == ["missing-first", "missing-last"]
    assert seen[0][0] == ["missing-first", "draft", "1706.03762", "missing-last"]
    assert len(seen) == 1
    assert loop_threads and seen[0][1] not in loop_threads


def test_corpus_validation_accepts_the_documented_id_count_and_length_limits(tmp_path, monkeypatch):
    seen = []

    class MissingCorpus:
        def records(self, ids):
            seen.extend(ids)
            return []

    monkeypatch.setattr(server, "load", lambda: SimpleNamespace(dsn=MissingCorpus()))
    ids = [f"{number:04d}" + "x" * 76 for number in range(1000)]
    with TestClient(application(tmp_path)) as client:
        response = client.post(ENDPOINT, json={"ids": ids})
    assert response.status_code == 200
    assert response.json() == {"papers": [], "missing": ids}
    assert seen == ids


def test_read_only_frontend_role_does_not_expose_corpus_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load", forbid_load)
    with TestClient(application(tmp_path, role="frontend")) as client:
        assert client.post(ENDPOINT, json={"ids": ["1706.03762"]}).status_code == 404
