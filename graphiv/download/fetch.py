"""
On-demand full-text fetch: the local store first, then arXiv or ar5iv, write-through

It lives in download because it is acquisition, and the later stages reach it through here
A miss costs one polite rate-limited request and is then cached on disk forever
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

from graphiv.download._common import HTML_DIR, PDF_DIR

_UA = "GraphIV/0.1 (grounded literature-review engine over arXiv; research use)"
_MIN_INTERVAL = 3.0
_TIMEOUT = 45.0

_enabled: bool = True
_last_hit: dict[str, float] = {}


def set_enabled(on: bool) -> None:
    """
    Toggle lazy network fetching (config `fetch`); a local hit is still returned either way
    """
    global _enabled  # noqa: PLW0603
    _enabled = on


def _get(url: str, host: str) -> bytes | None:
    """
    Rate-limited GET (per-host token wait); None on any HTTP/network failure
    """
    wait = _last_hit.get(host, 0.0) + _MIN_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _stem_yymm(arxiv_id: str) -> tuple[str, str]:
    """
    (filename stem, YYMM dir name), mirrors the bulk on-disk naming
    """
    if "/" in arxiv_id:
        arch, num = arxiv_id.split("/", 1)
        return f"{arch}{num}", num[:4]
    return arxiv_id, arxiv_id[:4]


def local_html(arxiv_id: str) -> Path | None:
    """
    The on-disk LaTeXML render for an id, or None when it was never fetched

    Args:
        arxiv_id: The arxiv id, new or old style.

    Returns:
        The path under HTML_DIR, or None.
    """
    stem, yymm = _stem_yymm(arxiv_id)
    p = HTML_DIR / yymm / f"{stem}.html"
    return p if p.is_file() else None


def fetch_html(arxiv_id: str) -> Path | None:
    """
    The local LaTeXML render, else fetch one from ar5iv or arxiv.org into HTML_DIR/<YYMM>/
    """
    local = local_html(arxiv_id)
    if local is not None or not _enabled:
        return local
    body = _get(f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", "ar5iv")
    # a successful LaTeXML render carries ltx_ classes; misses redirect to abs
    if body is None or b"ltx_" not in body:
        body = _get(f"https://arxiv.org/html/{arxiv_id}", "arxiv")
    if body is None or b"ltx_" not in body:
        return None
    stem, yymm = _stem_yymm(arxiv_id)
    dest = HTML_DIR / yymm / f"{stem}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = dest.write_bytes(body)
    print(f"  [fetch] html arXiv:{arxiv_id} ({len(body) // 1024} KB)", flush=True)
    return dest


def local_pdf(arxiv_id: str) -> Path | None:
    """
    Best on-disk PDF for an id: highest bulk-downloaded version, else the lazy-fetched copy
    """
    stem, yymm = _stem_yymm(arxiv_id)
    d = PDF_DIR / yymm
    if not d.is_dir():
        return None
    best: Path | None = None
    best_v = -1
    for p in d.glob(f"{stem}v*.pdf"):
        try:
            v = int(p.stem[len(stem) + 1 :])
        except ValueError:
            continue
        if v > best_v:
            best_v, best = v, p
    if best is not None:
        return best
    plain = d / f"{stem}.pdf"
    return plain if plain.is_file() else None


def fetch_pdf(arxiv_id: str) -> Path | None:
    """
    The local PDF, else fetch the latest version into PDF_DIR/<YYMM>/ and return the path
    """
    local = local_pdf(arxiv_id)
    if local is not None or not _enabled:
        return local
    body = _get(f"https://arxiv.org/pdf/{arxiv_id}", "arxiv")
    if body is None or not body.startswith(b"%PDF-"):
        return None
    stem, yymm = _stem_yymm(arxiv_id)
    dest = PDF_DIR / yymm / f"{stem}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = dest.write_bytes(body)
    print(f"  [fetch] pdf arXiv:{arxiv_id} ({len(body) // 1024} KB)", flush=True)
    return dest
