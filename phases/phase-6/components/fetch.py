"""On-demand full-text fetch: local store first, then arXiv/ar5iv, write-through.

The release dump ships no PDFs/HTML, so a restored install fetches per-paper full text
lazily into the same `data/pdf|html/<YYMM>/` layout phases 1-2 build — one polite,
rate-limited request per miss (~1 req/3s per host), cached forever on disk. Toggle with
config `fetch` (run.py calls `set_enabled`).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

from _common import HTML_DIR, PDF_DIR

_UA = "GraphIV/0.1 (grounded literature-review engine over arXiv; research use)"
_MIN_INTERVAL = 3.0
_TIMEOUT = 45.0

_enabled: bool = True
_last_hit: dict[str, float] = {}


def set_enabled(on: bool) -> None:
    global _enabled  # noqa: PLW0603
    _enabled = on


def _get(url: str, host: str) -> bytes | None:
    """Rate-limited GET (per-host token wait); None on any HTTP/network failure."""
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
    """(filename stem, YYMM dir name) — mirrors the phase-1/2 on-disk naming."""
    if "/" in arxiv_id:  # legacy: hep-th/9201002 -> hep-th9201002 in 9201/
        arch, num = arxiv_id.split("/", 1)
        return f"{arch}{num}", num[:4]
    return arxiv_id, arxiv_id[:4]


def fetch_html(arxiv_id: str) -> Path | None:
    """Fetch the LaTeXML render (ar5iv, else arxiv.org native HTML) into
    `HTML_DIR/<YYMM>/` and return the path, or None."""
    if not _enabled:
        return None
    body = _get(f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", "ar5iv")
    # a successful LaTeXML render carries ltx_ classes; misses redirect to a plain abs page
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
    """Best on-disk PDF for an id: highest phase-1 version, else the lazy-fetched copy."""
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
    """Fetch the latest-version PDF into `PDF_DIR/<YYMM>/` and return the path, or None."""
    if not _enabled:
        return None
    body = _get(f"https://arxiv.org/pdf/{arxiv_id}", "arxiv")
    if body is None or not body.startswith(b"%PDF-"):
        return None
    stem, yymm = _stem_yymm(arxiv_id)
    dest = PDF_DIR / yymm / f"{stem}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = dest.write_bytes(body)
    print(f"  [fetch] pdf arXiv:{arxiv_id} ({len(body) // 1024} KB)", flush=True)
    return dest
