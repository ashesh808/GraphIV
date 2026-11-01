"""The offline manager serves its local UI without starting maintenance jobs."""

from types import SimpleNamespace
from typing import cast

from starlette.applications import Starlette
from starlette.testclient import TestClient

from offline.manager.routes import routes
from offline.manager.schedule import Manager


def test_manager_assets_are_served_from_the_offline_component() -> None:
    manager = cast(Manager, SimpleNamespace())
    with TestClient(Starlette(routes=routes(manager))) as client:
        for path in ("/", "/app.js", "/style.css", "/icon.svg"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.content, path
