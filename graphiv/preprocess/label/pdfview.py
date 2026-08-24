"""
Locate a citation sentence inside its paper's PDF and render that page

A PDF breaks lines mid-phrase, so the page is chosen by word-gram overlap, not by substring
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pymupdf

# a gram this long is distinctive without spanning the line breaks that defeat a substring search
GRAM: int = 4
# the share of the sentence's grams a page must carry before it counts as the right page
MIN_OVERLAP: float = 0.25
# highlight windows are short so they survive extraction, and wide enough to not match everywhere
HILITE_WORDS: int = 5
# the dashboard's yellow, as the fraction triple a PDF annotation wants
HILITE_RGB: tuple[float, float, float] = (0.973, 0.816, 0.416)

_WORD = re.compile(r"[a-z][a-z\-']{1,}")

# MuPDF reports malformed color spaces per page, which says nothing about the text
_ = pymupdf.TOOLS.mupdf_display_errors(False)


@dataclass(frozen=True)
class Located:
    """
    Where a sentence was found, and the boxes that cover the fragments that matched
    """

    page: int
    rects: list[tuple[float, float, float, float]]
    needles: list[str]
    overlap: float


def _words(text: str) -> list[str]:
    """
    Lowercased word tokens, with soft hyphenation joined back up
    """
    return _WORD.findall(text.lower().replace("-\n", "").replace("\n", " "))


def _grams(words: list[str], n: int = GRAM) -> set[str]:
    """
    The set of word n-grams, which survives a line break that a substring search does not
    """
    return {" ".join(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def _highlight(
    page: pymupdf.Page, words: list[str]
) -> tuple[list[tuple[float, float, float, float]], list[str]]:
    """
    Boxes and phrases for whichever short windows of the sentence the page actually renders
    """
    rects: list[tuple[float, float, float, float]] = []
    matched: list[str] = []
    for start in range(0, max(1, len(words) - HILITE_WORDS + 1), HILITE_WORDS):
        phrase = " ".join(words[start : start + HILITE_WORDS])
        if len(phrase) < 12:
            continue
        hits = page.search_for(phrase)
        if hits:
            matched.append(phrase)
        for r in hits:
            rects.append((r.x0, r.y0, r.x1, r.y1))
    return rects, matched


def locate(doc: pymupdf.Document, sentence: str) -> Located | None:
    """
    The page carrying most of the sentence, with boxes over the fragments that matched
    """
    words = _words(sentence)
    wanted = _grams(words)
    if not wanted:
        return None
    best_page, best_overlap = -1, 0.0
    for page_no in range(doc.page_count):
        text = cast(str, doc[page_no].get_text())
        share = len(wanted & _grams(_words(text))) / len(wanted)
        if share > best_overlap:
            best_page, best_overlap = page_no, share
    if best_page < 0 or best_overlap < MIN_OVERLAP:
        return None
    rects, matched = _highlight(doc[best_page], words)
    return Located(best_page, rects, matched, best_overlap)


def render(
    doc: pymupdf.Document,
    page: int,
    rects: list[tuple[float, float, float, float]] | None = None,
    zoom: float = 2.0,
) -> bytes:
    """
    One page as PNG bytes, with the given boxes drawn over it as highlights
    """
    p = doc[page]
    if rects:
        for x0, y0, x1, y1 in rects:
            annot = p.add_highlight_annot(pymupdf.Rect(x0, y0, x1, y1))
            annot.set_colors(stroke=HILITE_RGB)
            annot.update()
    pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    png = cast(bytes, pix.tobytes("png"))
    if rects:
        for annot in list(p.annots()):
            p.delete_annot(annot)
    return png


def open_pdf(path: Path) -> pymupdf.Document | None:
    """
    Open a PDF, returning None when it is missing or unreadable
    """
    if not path.is_file():
        return None
    try:
        return pymupdf.open(path)
    # a truncated or encrypted download must not stop the labeling session
    except Exception as e:  # noqa: BLE001
        print(f"  pdf open failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return None
