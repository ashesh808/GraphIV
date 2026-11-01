"""The legacy dashboard stays available through the runtime application."""

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from apps.api.dashboard import mount


@pytest.fixture
def dashboard(tmp_path: Path) -> TestClient:
    server = FastMCP("test-dashboard")
    mount(server, tmp_path / "runs", tmp_path / "pdfs")
    return TestClient(server.streamable_http_app())


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/", "text/html"),
        ("/app.js", "javascript"),
        ("/style.css", "text/css"),
        ("/icon.svg", "image/svg+xml"),
        ("/vendor/marked.min.js", "javascript"),
    ],
)
def test_dashboard_assets(dashboard: TestClient, path: str, content_type: str) -> None:
    response = dashboard.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.content


def test_dashboard_without_a_store(dashboard: TestClient) -> None:
    response = dashboard.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []
