"""
Where one paper's full text sits on disk, fetched from arXiv when the store never had it

A fetched paper lands in the corpus itself, under the YYMM directory the bulk store uses
The wait between requests blocks the calling thread, which is a tool worker and not the loop
"""

from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

LOG = logging.getLogger(__name__)

MODERN = re.compile(r"^(\d{2})(\d{2})\.(\d{4,5})")
LEGACY = re.compile(r"^[a-z-]+(?:\.[A-Z]{2})?/(\d{2})(\d{2})(\d{3})")

AGENT = "GraphIV/0.2 (grounded literature review over arXiv; research use)"
# arXiv asks for one request every three seconds
INTERVAL = 3.0
TIMEOUT = 45.0
HTML_URLS = (
    ("ar5iv.labs.arxiv.org", "https://ar5iv.labs.arxiv.org/html/{}"),
    ("arxiv.org", "https://arxiv.org/html/{}"),
)
PDF_URL = "https://arxiv.org/pdf/{}"
# a LaTeXML render carries ltx_ classes, and a paper with no render redirects to its abstract
RENDERED = b"ltx_"
PDF_MAGIC = b"%PDF-"

WAITED: dict[str, float] = {}


def yymm(arxiv_id: str) -> str | None:
    """
    The directory a paper sits in

    Args:
        arxiv_id: A modern or legacy arXiv id.

    Returns:
        The four digit YYMM, or None when the id does not parse.
    """
    got = MODERN.match(arxiv_id) or LEGACY.match(arxiv_id)
    return f"{got.group(1)}{got.group(2)}" if got else None


def stem(arxiv_id: str) -> str:
    """
    The name a paper's files carry, which is the id with the legacy archive folded in

    Args:
        arxiv_id: A modern or legacy arXiv id.

    Returns:
        The file stem.
    """
    return arxiv_id.replace("/", "")


def html_path(root: Path, arxiv_id: str) -> Path | None:
    """
    Where one paper's html would sit under one root

    Args:
        root: An html store root.
        arxiv_id: The paper.

    Returns:
        The path, or None when the id does not parse.
    """
    found = yymm(arxiv_id)
    return None if found is None else root / found / f"{stem(arxiv_id)}.html"


def newest_pdf(root: Path, arxiv_id: str) -> Path | None:
    """
    The highest version of one paper's pdf under one root

    The bulk store names a file after the version it downloaded and a fetched copy carries none,
    so both spellings are looked for.

    Args:
        root: A pdf store root.
        arxiv_id: The paper.

    Returns:
        The path, or None when no version is there.
    """
    found = yymm(arxiv_id)
    if found is None or not (root / found).is_dir():
        return None
    name = stem(arxiv_id)
    versions: list[tuple[int, Path]] = []
    for path in (root / found).glob(f"{name}v*.pdf"):
        tail = path.stem[len(name) + 1 :]
        if tail.isdigit():
            versions.append((int(tail), path))
    if versions:
        return max(versions)[1]
    plain = root / found / f"{name}.pdf"
    return plain if plain.is_file() else None


def get(url: str, host: str) -> bytes | None:
    """
    One rate limited request, which never raises

    Args:
        url: What to ask for.
        host: The name the wait is counted against.

    Returns:
        The body, or None when the request failed.
    """
    wait = WAITED.get(host, 0.0) + INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    WAITED[host] = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            body: bytes = response.read()
            return body
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def fetch_html(corpus: Path, arxiv_id: str) -> Path | None:
    """
    One paper's html from ar5iv or arxiv.org, written into the corpus

    Args:
        corpus: The html store root, which this writes into.
        arxiv_id: The paper.

    Returns:
        The written path, or None when neither source rendered it.
    """
    dest = html_path(corpus, arxiv_id)
    if dest is None:
        return None
    for host, template in HTML_URLS:
        body = get(template.format(arxiv_id), host)
        if body is not None and RENDERED in body:
            dest.parent.mkdir(parents=True, exist_ok=True)
            _ = dest.write_bytes(body)
            LOG.info("fetched html %s, %d KB", arxiv_id, len(body) // 1024)
            return dest
    return None


def fetch_pdf(corpus: Path, arxiv_id: str) -> Path | None:
    """
    One paper's pdf from arxiv.org, written into the corpus

    Args:
        corpus: The pdf store root, which this writes into.
        arxiv_id: The paper.

    Returns:
        The written path, or None when the request failed or returned something else.
    """
    found = yymm(arxiv_id)
    if found is None:
        return None
    body = get(PDF_URL.format(arxiv_id), "arxiv.org")
    if body is None or not body.startswith(PDF_MAGIC):
        return None
    dest = corpus / found / f"{stem(arxiv_id)}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = dest.write_bytes(body)
    LOG.info("fetched pdf %s, %d KB", arxiv_id, len(body) // 1024)
    return dest


def html_file(corpus: Path, arxiv_id: str, fetch: bool = False) -> Path | None:
    """
    One paper's html, from the corpus and then arXiv

    Args:
        corpus: The html store root.
        arxiv_id: The paper.
        fetch: Whether a miss may reach the network.

    Returns:
        The path to read, or None when the paper has no html anywhere.
    """
    found = html_path(corpus, arxiv_id)
    if found is not None and found.is_file():
        return found
    return fetch_html(corpus, arxiv_id) if fetch else None


def pdf_file(corpus: Path, arxiv_id: str, fetch: bool = False) -> Path | None:
    """
    One paper's pdf, from the corpus and then arXiv

    Args:
        corpus: The pdf store root.
        arxiv_id: The paper.
        fetch: Whether a miss may reach the network.

    Returns:
        The path to read, or None when the paper has no pdf anywhere.
    """
    found = newest_pdf(corpus, arxiv_id)
    if found is not None:
        return found
    return fetch_pdf(corpus, arxiv_id) if fetch else None
