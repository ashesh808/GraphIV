"""Container bind overrides leave the shared runtime configuration intact."""

from apps.api import server
from src.mcp.state import serving


def test_frontend_bind_override_does_not_open_the_corpus(monkeypatch) -> None:
    settings = serving()
    observed = {}

    def run(page, transport):
        observed.update(host=page.settings.host, port=page.settings.port, transport=transport)

    def unexpected_load():
        raise AssertionError("The legacy frontend must not load the corpus")

    monkeypatch.setattr(server.FastMCP, "run", run)
    monkeypatch.setattr(server, "load", unexpected_load)
    server.run(http=True, role="frontend", host="0.0.0.0", port=8000)

    assert observed == {"host": "0.0.0.0", "port": 8000, "transport": "streamable-http"}
    assert serving() is settings
    assert (settings.host, settings.frontend_port) == ("127.0.0.1", 6969)
