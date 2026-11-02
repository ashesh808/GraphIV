"""Container bind overrides leave the shared runtime configuration intact."""

from apps.api import server
from src.mcp.state import serving


def test_frontend_bind_override_does_not_open_the_corpus(monkeypatch) -> None:
    settings = serving()
    observed = {}

    def run(app, *, host, port, access_log):
        observed.update(host=host, port=port, access_log=access_log)

    def unexpected_load():
        raise AssertionError("The legacy frontend must not load the corpus")

    monkeypatch.setattr(server.uvicorn, "run", run)
    monkeypatch.setattr(server, "load", unexpected_load)
    server.run(http=True, role="frontend", host="0.0.0.0", port=8000)

    assert observed == {"host": "0.0.0.0", "port": 8000, "access_log": False}
    assert serving() is settings
    assert (settings.host, settings.frontend_port) == ("127.0.0.1", 6969)
