"""HTTP starts without a corpus and authenticated jobs run serially with bounded state."""

import threading
import time
from dataclasses import replace

import pytest
from starlette.testclient import TestClient

from apps.api import server
from apps.api.orchestration import Coordinator, ResearchRequest, run_research
from src.mcp.state import serving
from src.storage.runs import LocalReportStore


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    for name in ("GRAPHIV_API_TOKEN", "GRAPHIV_REQUIRE_AUTH", "GRAPHIV_RUNTIME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, "READONLY", False)
    monkeypatch.setattr("src.mcp.state.prepare_runtime", lambda: None, raising=False)


def app(tmp_path, **kwargs):
    settings = replace(serving(), runs=tmp_path / "runs", pdfs=tmp_path / "pdfs")
    return server.build_http_app(settings, report_store=LocalReportStore(settings.runs), **kwargs)


def test_missing_corpus_keeps_liveness_and_empty_library(tmp_path, monkeypatch):
    def forbidden():
        raise AssertionError("HTTP startup must not load the corpus")

    monkeypatch.setattr(server, "load", forbidden)
    with TestClient(
        app(
            tmp_path,
            status_callback=lambda: {
                "ready": False,
                "reasons": ["No citation index is configured"],
            },
        )
    ) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["reasons"] == ["No citation index is configured"]
        assert client.get("/api/runs").json() == []
        rejected = client.post("/api/research", json={"question": "Citation graphs?"})
        assert rejected.status_code == 503
        assert "No citation index" in rejected.text


def test_bearer_token_protects_reads_mcp_and_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPHIV_API_TOKEN", "test-api-secret")
    with TestClient(
        app(tmp_path, status_callback=lambda: {"ready": True, "reasons": []}),
        base_url="http://127.0.0.1:6767",
    ) as client:
        assert client.get("/health/live").status_code == 200
        for path in ("/api/runs", "/mcp", "/api/jobs/missing"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert (
            client.get("/api/runs", headers={"Authorization": "Bearer test-api-secret"}).json()
            == []
        )
        initialized = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-api-secret",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "runtime-test", "version": "1"},
                },
            },
        )
        assert initialized.status_code == 200


def test_azure_missing_token_never_opens_unprotected_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPHIV_RUNTIME", "azure")
    with TestClient(
        app(tmp_path, status_callback=lambda: {"ready": True, "reasons": []})
    ) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.get("/api/runs").status_code == 503


def test_jobs_are_serial_bounded_and_keep_a_failure_reason(tmp_path):
    release = threading.Event()
    started = threading.Event()
    seen = []

    def runner(request):
        seen.append(request.question)
        if request.question == "First":
            started.set()
            assert release.wait(3)
            return {"slug": "first-report"}
        raise RuntimeError("Embedding service returned HTTP 401")

    jobs = Coordinator(runner, max_jobs=2, max_pending=2)
    with TestClient(
        app(tmp_path, status_callback=lambda: {"ready": True, "reasons": []}, coordinator=jobs)
    ) as client:
        first = client.post("/api/research", json={"question": "First"})
        assert first.status_code == 202
        assert started.wait(2)
        second = client.post("/api/research", json={"question": "Second"})
        assert second.status_code == 202
        assert client.post("/api/research", json={"question": "Third"}).status_code == 429
        assert seen == ["First"]
        release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = client.get(second.json()["status_url"]).json()
            if result["status"] == "failed":
                break
            time.sleep(0.01)
        assert result["status"] == "failed"
        assert result["error"] == "Embedding service returned HTTP 401"
        assert client.get(first.json()["status_url"]).json()["result"] == {"slug": "first-report"}
        assert seen == ["First", "Second"]


@pytest.mark.parametrize(
    "body",
    [
        {"question": " "},
        {"question": "x", "mode": "unknown"},
        {"question": "x", "effort": "unlimited"},
        {"question": "x", "api_key": "not-an-input"},
    ],
)
def test_research_validates_before_scheduling(tmp_path, body):
    jobs = Coordinator(lambda request: pytest.fail("Invalid input must not start work"))
    with TestClient(
        app(tmp_path, status_callback=lambda: {"ready": True, "reasons": []}, coordinator=jobs)
    ) as client:
        assert client.post("/api/research", json=body).status_code == 422
        assert not jobs.jobs


def test_coordinator_uses_existing_tools_and_preserves_mcp_state(monkeypatch, tmp_path):
    import json

    from src.mcp import retrieve, state, write_report

    handles = object()
    previous_rankings, previous_areas = state.STORE.copy(), state.AREAS.copy()
    previous = object()
    state.STORE["existing-mcp-ranking"] = previous

    def retrieval(current, **kwargs):
        assert current is handles
        assert kwargs == {
            "question": "How do citation graphs help?",
            "mode": "frontier",
            "effort": "deep",
        }
        assert not state.STORE
        state.STORE["owned-ranking"] = object()
        return json.dumps({"query_id": "owned-ranking"})

    def writing(current, **kwargs):
        assert current is handles
        assert kwargs["query_ids"] == ["owned-ranking"]
        assert kwargs["question"] == "How do citation graphs help?"
        assert kwargs["effort"] == "deep" and kwargs["end"] is True
        state.reset()
        return json.dumps(
            {
                "path": str(tmp_path / "saved-run/report.md"),
                "papers": 7,
                "answer": "Evidence",
                "report": "Full report is not retained in job status",
            }
        )

    monkeypatch.setattr(state, "load", lambda: handles)
    monkeypatch.setattr(retrieve, "retrieve", retrieval)
    monkeypatch.setattr(write_report, "write_report", writing)
    try:
        result = run_research(
            ResearchRequest(question="How do citation graphs help?", mode="frontier", effort="deep")
        )
        assert {key: result[key] for key in ("slug", "papers", "answer", "url")} == {
            "slug": "saved-run",
            "papers": 7,
            "answer": "Evidence",
            "url": "/api/runs/saved-run",
        }
        assert result["metrics"]["peak_rss_bytes"] > 0
        assert result["metrics"]["elapsed_seconds"] >= 0
        assert "report" not in result
        assert state.STORE["existing-mcp-ranking"] is previous
    finally:
        state.reset()
        state.STORE.update(previous_rankings)
        state.AREAS.update(previous_areas)


def test_runtime_preparation_does_not_block_http(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def prepare():
        started.set()
        assert release.wait(3)

    monkeypatch.setattr("src.mcp.state.prepare_runtime", prepare, raising=False)
    with TestClient(
        app(
            tmp_path,
            status_callback=lambda: {"ready": False, "reasons": ["Index download pending"]},
        )
    ) as client:
        try:
            assert started.wait(2)
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 503
        finally:
            release.set()


def test_mcp_model_work_does_not_block_health(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def slow_tool() -> str:
        started.set()
        assert release.wait(3)
        return "completed"

    monkeypatch.setattr(server, "_TOOL_BODIES", [(slow_tool, False)])
    headers = {"Accept": "application/json, text/event-stream"}
    with TestClient(
        app(tmp_path, status_callback=lambda: {"ready": True, "reasons": []}),
        base_url="http://127.0.0.1:6767",
    ) as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "runtime-test", "version": "1"},
                },
            },
        )
        headers["Mcp-Session-Id"] = initialized.headers["mcp-session-id"]
        client.post(
            "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        replies = []
        worker = threading.Thread(
            target=lambda: replies.append(
                client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {"name": "slow_tool", "arguments": {}},
                    },
                )
            )
        )
        worker.start()
        try:
            assert started.wait(2)
            before = time.monotonic()
            assert client.get("/health/live").status_code == 200
            assert time.monotonic() - before < 1
        finally:
            release.set()
            worker.join(3)
        assert len(replies) == 1 and replies[0].status_code == 200
        assert "completed" in replies[0].text


def test_mcp_tools_wait_for_runtime_preparation(tmp_path, monkeypatch):
    def never_load() -> str:
        pytest.fail("An unready tool must not trigger a duplicate corpus load")

    monkeypatch.setattr(server, "_TOOL_BODIES", [(never_load, False)])
    headers = {"Accept": "application/json, text/event-stream"}
    with TestClient(
        app(
            tmp_path,
            status_callback=lambda: {"ready": False, "reasons": ["Corpus preparation pending"]},
        ),
        base_url="http://127.0.0.1:6767",
    ) as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "runtime-test", "version": "1"},
                },
            },
        )
        headers["Mcp-Session-Id"] = initialized.headers["mcp-session-id"]
        client.post(
            "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "never_load", "arguments": {}},
            },
        )
        assert response.status_code == 200
        assert "Corpus preparation pending" in response.text
        assert '"isError":true' in response.text
