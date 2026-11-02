"""Parsing/guard unit checks only; these never simulate a passing deployment receipt."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from offline.index_build.verify_deployment import (
    VerificationError,
    _database_records,
    _sentences,
    job_counts,
    origin,
    report_identifiers,
    require_job_identity,
    require_ready,
    validate_job_ids,
    validate_provenance,
    verify_deployment,
)


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",
        "https://token@example.com",
        "https://example.com/api",
        "https://example.com?token=secret",
        "https://example.com/#fragment",
        "file:///tmp/api",
    ],
)
def test_origins_reject_credentials_paths_and_nonlocal_cleartext(value):
    with pytest.raises(ValueError):
        origin(value)


def test_origin_accepts_canonical_https_and_local_development():
    assert origin("https://api.example.com/") == "https://api.example.com"
    assert origin("http://127.0.0.1:6969") == "http://127.0.0.1:6969"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (503, {"ready": False, "reasons": ["Corpus not published"]}),
        (200, {"ready": False}),
        (200, {"ready": True, "reasons": ["Model not loaded"]}),
        (200, {"ready": True, "scope": "saved-reports"}),
        (200, {"ready": 1}),
    ],
)
def test_readiness_guard_never_accepts_missing_corpus_or_library_only(code, status):
    with pytest.raises(VerificationError):
        require_ready(code, status)


def test_unready_reason_redacts_configured_token(monkeypatch):
    monkeypatch.setenv("GRAPHIV_API_TOKEN", "token-from-environment")
    with pytest.raises(VerificationError) as failed:
        require_ready(503, {"ready": False, "reasons": ["token-from-environment rejected"]})
    assert "token-from-environment" not in str(failed.value)
    assert "[redacted]" in str(failed.value)


def test_count_parser_requires_real_explicit_fields_and_rejects_boolean_counts():
    with pytest.raises(VerificationError, match="Mining counts"):
        job_counts({"retrieval_counts": {"pool": 7, "kept": 2}})
    with pytest.raises(VerificationError, match="Mining successors"):
        job_counts(
            {
                "retrieval_counts": {"pool": 7, "kept": 2},
                "mining_counts": {"edges": 8, "lineages": 1, "successors": True},
            }
        )
    with pytest.raises(VerificationError, match="Retrieval pool"):
        job_counts(
            {
                "retrieval_counts": {"kept": 2},
                "mining_counts": {"edges": 8, "lineages": 1, "successors": 0},
            }
        )


def test_absent_provenance_is_never_a_published_corpus():
    with pytest.raises(VerificationError, match="Run corpus provenance"):
        validate_provenance(None)


def test_recursive_sentence_guard_detects_unpublished_text_only():
    assert _sentences({"edges": [{"sentence": ""}], "note": "Title wording"}) == []
    assert _sentences({"lineages": [{"edges": [{"sentence": "Unpublished quote"}]}]}) == [
        "Unpublished quote"
    ]


def test_report_identifier_parser_includes_citations_and_nested_graph_lineage_records():
    def encoded(value):
        return json.dumps(value).encode()

    artifacts = {
        "report.md": b"A citation [arXiv:2001.00001](https://arxiv.org/abs/2001.00001).",
        "run.json": encoded({"papers": ["2001.00002"], "cited": ["2001.00001"]}),
        "papers.json": encoded([{"arxiv_id": "2001.00002"}]),
        "graph.json": encoded(
            {
                "nodes": [{"arxiv_id": "2001.00002"}],
                "edges": [{"source": "2001.00002", "target": "2001.00003"}],
            }
        ),
        "report.json": encoded({"lineages": [{"papers": [{"arxiv_id": "2001.00004"}]}]}),
    }
    assert report_identifiers(artifacts) == {
        "2001.00001",
        "2001.00002",
        "2001.00003",
        "2001.00004",
    }


def test_independent_sqlite_lookup_is_read_only_and_preserves_author_identity(tmp_path: Path):
    database = tmp_path / "metadata.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE papers(arxiv_id TEXT,title TEXT,authors TEXT)")
        connection.execute("INSERT INTO papers VALUES ('2001.00001','Stored title','Ada Reader')")
    records = _database_records(database, {"2001.00001", "outside"})
    assert records == {"2001.00001": {"title": "Stored title", "authors": "Ada Reader"}}
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM papers").fetchone()[0] == 1


def test_duplicate_questions_are_rejected_before_creating_receipts(tmp_path: Path):
    with pytest.raises(ValueError):
        verify_deployment(
            "https://api.example.com",
            "https://web.example.com",
            tmp_path / "receipt",
            questions=["Same question", "Same question"],
        )
    assert not (tmp_path / "receipt").exists()


@pytest.mark.parametrize(
    "identifiers",
    [
        [],
        ["a" * 32],
        ["a" * 32] * 2,
        ["a" * 32, "b" * 32, "c" * 32],
        ["a" * 32, "../other"],
        ["a" * 32, "not-a-generated-job-id"],
    ],
)
def test_existing_job_id_guards_run_before_any_receipt_or_http(tmp_path: Path, identifiers):
    with pytest.raises(ValueError, match="two distinct"):
        verify_deployment(
            "https://api.example.com",
            "https://web.example.com",
            tmp_path / "receipt",
            job_ids=identifiers,
        )
    assert not (tmp_path / "receipt").exists()


def test_existing_job_mode_requires_exactly_two_distinct_server_ids():
    assert validate_job_ids(None) is None
    assert validate_job_ids(["a" * 32, "b" * 32]) == ["a" * 32, "b" * 32]


@pytest.mark.parametrize("field", ["id", "question", "mode", "effort"])
def test_existing_job_identity_rejects_each_mismatched_input(field):
    expected = {
        "id": "a" * 32,
        "question": "Exact question?",
        "mode": "survey",
        "effort": "standard",
    }
    observed = dict(expected, **{field: "different"})
    with pytest.raises(VerificationError, match=f"job {field} does not match"):
        require_job_identity(
            observed,
            job_id=expected["id"],
            question=expected["question"],
            mode=expected["mode"],
            effort=expected["effort"],
        )
