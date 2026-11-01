"""
The snapshot fetch against a local server: a whole download, a resume, a stop, and the commit
"""

import http.server
import json
import threading
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from offline.manager import snapshot


def records(count: int) -> bytes:
    """
    A small snapshot in the real layout, numeric ids first and one old slash id last
    """
    rows = [
        {"id": f"2609.{i:05d}", "versions": [{"created": "Fri, 25 Sep 2026 10:00:00 GMT"}]}
        for i in range(count)
    ]
    rows.append({"id": "hep-th/9901001", "versions": [{"created": "Fri, 1 Jan 1999 10:00:00 GMT"}]})
    return "\n".join(json.dumps(r) for r in rows).encode() + b"\n"


class Serve(http.server.BaseHTTPRequestHandler):
    """
    Serves one zip with an etag and range support, as the signed storage url does
    """

    body = b""

    def do_GET(self) -> None:
        start = 0
        said = self.headers.get("Range", "")
        if said.startswith("bytes="):
            start = int(said[6:].split("-")[0])
        chunk = self.body[start:]
        self.send_response(206 if start else 200)
        self.send_header("ETag", '"same"')
        self.send_header("Content-Length", str(len(chunk)))
        self.end_headers()
        _ = self.wfile.write(chunk)

    def log_message(self, format: str, *args: object) -> None:
        _ = format, args


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    """
    A zip holding the small snapshot, served on a free local port
    """
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("arxiv-metadata-oai-snapshot.json", records(3000))
    Serve.body = archive.read_bytes()
    httpd = http.server.HTTPServer(("127.0.0.1", 0), Serve)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/download"
    httpd.shutdown()


def test_fetch_stages_and_commits(tmp_path: Path, server: str) -> None:
    data = tmp_path / "data"
    data.mkdir()
    current = data / "arxiv.json"
    _ = current.write_bytes(records(10))
    log = tmp_path / "log"
    said = snapshot.fetch(current, server, log, threading.Event())
    assert said["newest"] == "2026-09-25"
    assert (data / "arxiv-new.json").exists() and not (data / "arxiv-new.zip").exists()
    assert "/" in log.read_text() and "staged" in log.read_text()
    snapshot.commit(current, log)
    assert current.read_bytes() == records(3000)
    assert not (data / "arxiv-new.json").exists()


def test_resume_from_partial(tmp_path: Path, server: str) -> None:
    data = tmp_path / "data"
    data.mkdir()
    current = data / "arxiv.json"
    half = len(Serve.body) // 2
    _ = (data / "arxiv-new.zip.part").write_bytes(Serve.body[:half])
    _ = (data / "arxiv-new.zip.part.etag").write_text("same")
    log = tmp_path / "log"
    said = snapshot.fetch(current, server, log, threading.Event())
    assert f"resuming at {half:,}" in log.read_text()
    assert said["newest"] == "2026-09-25"


def test_changed_source_starts_over(tmp_path: Path, server: str) -> None:
    data = tmp_path / "data"
    data.mkdir()
    current = data / "arxiv.json"
    _ = (data / "arxiv-new.zip.part").write_bytes(b"from an older version")
    _ = (data / "arxiv-new.zip.part.etag").write_text("older")
    log = tmp_path / "log"
    said = snapshot.fetch(current, server, log, threading.Event())
    assert "starting over" in log.read_text()
    assert said["newest"] == "2026-09-25"


def test_stop_keeps_the_partial(tmp_path: Path, server: str) -> None:
    data = tmp_path / "data"
    data.mkdir()
    halt = threading.Event()
    halt.set()
    with pytest.raises(InterruptedError):
        _ = snapshot.fetch(data / "arxiv.json", server, tmp_path / "log", halt)
    assert (data / "arxiv-new.zip.part").exists()
    assert not (data / "arxiv-new.json").exists()
    assert snapshot.info(data / "arxiv.json")["partial"]["total"] == len(Serve.body)
    assert snapshot.discard(data / "arxiv.json")
    assert not (data / "arxiv-new.zip.part").exists()
