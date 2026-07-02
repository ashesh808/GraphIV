"""PDF page rendering for the figure-reading lever (P0 spike, later P3).

The narrator/extractor only ever saw text. arXiv figures (architecture diagrams, result
plots) carry information no abstract states. Here we resolve a paper's on-disk PDF and
render pages to PNG bytes so a vision model can read them.

Layout (data/pdf -> vault): modern `2006.11239` -> pdf/2006/2006.11239v2.pdf ;
legacy `hep-th/9201002` -> pdf/9201/hep-th9201002v1.pdf . Multiple versions may exist;
we pick the highest `vN`.

`render_page` returns PNG bytes (no temp files). `figure_regions` is a stub for P3
caption-aware cropping.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF  # pyright: ignore[reportMissingTypeStubs]

from _common import PDF_DIR  # noqa: E402
from fetch import fetch_pdf  # noqa: E402

_VER: re.Pattern[str] = re.compile(r"v(\d+)\.pdf$")


def _stem_and_dir(arxiv_id: str) -> tuple[str, Path]:
    """(filename stem without version, YYMM dir) for a modern or legacy id."""
    if "/" in arxiv_id:  # legacy: hep-th/9201002 -> 9201 / hep-th9201002
        arch, num = arxiv_id.split("/", 1)
        return f"{arch}{num}", PDF_DIR / num[:4]
    return arxiv_id, PDF_DIR / arxiv_id[:4]  # modern: 2006.11239 -> 2006 / 2006.11239


def pdf_path(arxiv_id: str) -> Path | None:
    """Resolve the highest-version on-disk PDF; on a local miss, lazily fetch from arXiv."""
    stem, ddir = _stem_and_dir(arxiv_id)
    if ddir.is_dir():
        best: tuple[int, Path] | None = None
        for p in ddir.glob(f"{stem}v*.pdf"):
            m = _VER.search(p.name)
            ver = int(m.group(1)) if m else 0
            if best is None or ver > best[0]:
                best = (ver, p)
        if best is not None:
            return best[1]
        # some dumps drop the version suffix entirely
        flat = ddir / f"{stem}.pdf"
        if flat.exists():
            return flat
    return fetch_pdf(arxiv_id)


def page_count(arxiv_id: str) -> int:
    p = pdf_path(arxiv_id)
    if p is None:
        return 0
    with fitz.open(p) as doc:  # pyright: ignore[reportUnknownMemberType]
        return doc.page_count


def render_page(arxiv_id: str, page: int = 0, dpi: int = 150) -> bytes | None:
    """Render one page to PNG bytes (1-based pages clamped to range), or None."""
    p = pdf_path(arxiv_id)
    if p is None:
        return None
    try:
        with fitz.open(p) as doc:  # pyright: ignore[reportUnknownMemberType]
            n = doc.page_count
            if n == 0:
                return None
            idx = max(0, min(page, n - 1))
            pg = doc.load_page(idx)  # pyright: ignore[reportUnknownMemberType]
            pix = pg.get_pixmap(dpi=dpi)  # pyright: ignore[reportUnknownMemberType]
            data: bytes = pix.tobytes("png")  # pyright: ignore[reportUnknownMemberType]
            return data
    except Exception:  # noqa: BLE001  (corrupt/locked PDFs are skippable)
        return None


def pdf_text(arxiv_id: str, max_chars: int = 40000) -> str | None:
    """Concatenated page text from the on-disk PDF (for deep per-paper critique), or None.

    Reads native PDF text streams page by page up to `max_chars`. Used when ar5iv HTML is
    unavailable or when the critique wants the whole paper, not just salient sections.
    """
    p = pdf_path(arxiv_id)
    if p is None:
        return None
    try:
        parts: list[str] = []
        total = 0
        with fitz.open(p) as doc:  # pyright: ignore[reportUnknownMemberType]
            for i in range(doc.page_count):
                pg = doc.load_page(i)  # pyright: ignore[reportUnknownMemberType]
                raw: Any = pg.get_text()  # pyright: ignore[reportUnknownMemberType]
                txt = str(raw)
                parts.append(txt)
                total += len(txt)
                if total >= max_chars:
                    break
    except Exception:  # noqa: BLE001  (corrupt/locked PDFs are skippable)
        return None
    joined = "\n".join(parts).strip()
    return joined[:max_chars] if joined else None


def figure_regions(
    arxiv_id: str, page: int = 0
) -> list[tuple[float, float, float, float]]:
    """Stub for P3: bounding boxes of figure/image regions on a page (x0,y0,x1,y1)."""
    p = pdf_path(arxiv_id)
    if p is None:
        return []
    boxes: list[tuple[float, float, float, float]] = []
    try:
        with fitz.open(p) as doc:  # pyright: ignore[reportUnknownMemberType]
            if doc.page_count == 0:
                return []
            pg = doc.load_page(
                max(0, min(page, doc.page_count - 1))
            )  # pyright: ignore[reportUnknownMemberType]
            infos: list[Any] = (
                pg.get_image_info()
            )  # pyright: ignore[reportUnknownMemberType]
            for img in infos:
                bbox: Any = img.get("bbox")  # pyright: ignore[reportAny]
                if bbox:
                    boxes.append(
                        (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
                    )
    except Exception:  # noqa: BLE001
        return []
    return boxes
