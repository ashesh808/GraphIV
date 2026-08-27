"""
The acquisition helpers resolve a local file before they consider the network

The store paths are redirected at the module, so nothing here touches the real vault or arXiv
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphiv.download import fetch


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    An empty html and pdf store, with network fetching left on so a miss would be visible
    """
    html, pdf = tmp_path / "html", tmp_path / "pdf"
    (html / "1706").mkdir(parents=True)
    (pdf / "1706").mkdir(parents=True)
    monkeypatch.setattr(fetch, "HTML_DIR", html)
    monkeypatch.setattr(fetch, "PDF_DIR", pdf)

    def no_network(*_a: object, **_k: object) -> bytes | None:
        raise AssertionError("reached the network on a local hit")

    monkeypatch.setattr(fetch, "_get", no_network)
    monkeypatch.setattr(fetch, "_enabled", True)
    return tmp_path


def test_local_html_finds_a_stored_render(store: Path) -> None:
    p = store / "html" / "1706" / "1706.03762.html"
    _ = p.write_text("<html>ltx_</html>")
    assert fetch.local_html("1706.03762") == p


def test_local_html_is_none_when_absent(store: Path) -> None:
    assert fetch.local_html("1706.99999") is None


def test_local_html_handles_an_old_style_id(store: Path) -> None:
    (store / "html" / "9901").mkdir(parents=True)
    p = store / "html" / "9901" / "math9901001.html"
    _ = p.write_text("<html>ltx_</html>")
    assert fetch.local_html("math/9901001") == p


def test_fetch_html_returns_the_local_file_without_the_network(store: Path) -> None:
    """
    The stub _get raises, so reaching it at all fails the test
    """
    p = store / "html" / "1706" / "1706.03762.html"
    _ = p.write_text("<html>ltx_</html>")
    assert fetch.fetch_html("1706.03762") == p


def test_fetch_html_serves_a_local_hit_while_disabled(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The regression this guards: a disabled fetcher used to refuse local files too
    """
    monkeypatch.setattr(fetch, "_enabled", False)
    p = store / "html" / "1706" / "1706.03762.html"
    _ = p.write_text("<html>ltx_</html>")
    assert fetch.fetch_html("1706.03762") == p


def test_fetch_html_is_none_on_a_miss_while_disabled(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_enabled", False)
    assert fetch.fetch_html("1706.99999") is None


def test_fetch_pdf_serves_a_local_hit_while_disabled(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_enabled", False)
    p = store / "pdf" / "1706" / "1706.03762v3.pdf"
    _ = p.write_bytes(b"%PDF-1.4")
    assert fetch.fetch_pdf("1706.03762") == p


def test_local_pdf_prefers_the_highest_version(store: Path) -> None:
    for v in (1, 3, 2):
        _ = (store / "pdf" / "1706" / f"1706.03762v{v}.pdf").write_bytes(b"%PDF-1.4")
    got = fetch.local_pdf("1706.03762")
    assert got is not None and got.name == "1706.03762v3.pdf"


def test_local_pdf_falls_back_to_an_unversioned_file(store: Path) -> None:
    p = store / "pdf" / "1706" / "1706.03762.pdf"
    _ = p.write_bytes(b"%PDF-1.4")
    assert fetch.local_pdf("1706.03762") == p
