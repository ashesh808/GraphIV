"""
Structured contribution, method and result snippets pulled from ar5iv HTML

An abstract clip caps how much substance the writer can say about a paper
"""

from __future__ import annotations

import re
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser  # pyright: ignore[reportMissingImports]

from graphiv.core.settings import HTML_DIR
from graphiv.download.fetch import fetch_html

_WS = re.compile(r"\s+")
_LEAD_NUM = re.compile(r"^\s*\d+(\.\d+)*\s*")  # "4Experiments" / "4.1 Setup" -> strip

# section-title keyword buckets (checked lowercased, in priority order)
_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    ("intro", ("introduction",)),
    (
        "method",
        (
            "method",
            "approach",
            "architecture",
            "framework",
            "algorithm",
            "formulation",
            "proposed",
            "our model",
            "our method",
            "design",
            "model",
            "network",
        ),
    ),
    (
        "results",
        ("experiment", "result", "evaluation", "empirical", "ablation", "benchmark"),
    ),
    ("conclusion", ("conclusion", "discussion")),
]


def html_path(arxiv_id: str) -> Path | None:
    """
    Resolve the on-disk HTML for an arxiv id; on a local miss, lazily fetch from ar5iv
    """
    if "/" in arxiv_id:
        arch, num = arxiv_id.split("/", 1)
        yymm = num[:4]
        p = HTML_DIR / yymm / f"{arch}{num}.html"
    else:
        yymm = arxiv_id[:4]
        p = HTML_DIR / yymm / f"{arxiv_id}.html"
    return p if p.exists() else fetch_html(arxiv_id)


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _bucket_of(title: str) -> str | None:
    t = title.lower()
    for name, keys in _BUCKETS:
        if any(k in t for k in keys):
            return name
    return None


def parse_sections(
    arxiv_id: str,
) -> tuple[str, list[tuple[str, str | None, str]]] | None:
    """
    Return (abstract, [(title, bucket, text), ...]) or None if missing/unparseable
    """
    p = html_path(arxiv_id)
    if p is None:
        return None
    try:
        html = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    tree = LexborHTMLParser(html)
    # MathML renders doubled through .text(), so math and float nodes go before extraction
    for junk in tree.css("math, .ltx_Math, .ltx_equation, .ltx_tabular, cite"):
        junk.decompose()
    ab_node = tree.css_first("div.ltx_abstract")
    abstract = ""
    if ab_node is not None:
        # drop the "Abstract" title node text if present
        abstract = _clean(ab_node.text())
        abstract = re.sub(r"^Abstract\s*", "", abstract)
    sections: list[tuple[str, str | None, str]] = []
    for s in tree.css("section.ltx_section"):
        h = s.css_first("h2")
        title = _LEAD_NUM.sub("", _clean(h.text())) if h else ""
        paras = [_clean(pp.text()) for pp in s.css("p.ltx_p")]
        text = " ".join(t for t in paras if t)
        if text:
            sections.append((title, _bucket_of(title), text))
    return abstract, sections


def _first_chars(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    cut = text[:n]
    # back off to a sentence/space boundary
    dot = cut.rfind(". ")
    return (cut[: dot + 1] if dot > n * 0.5 else cut.rstrip()) + " …"


def extract_salient(
    arxiv_id: str,
    abstract_chars: int = 600,
    intro_chars: int = 700,
    method_chars: int = 900,
    results_chars: int = 700,
) -> str | None:
    """
    Compact structured snippet: ABSTRACT / CONTRIBUTION / METHOD / RESULTS

        Picks the first section matching each bucket; the intro's *last* paragraph
        usually states contributions, so we take both ends of the intro. Returns None
        if the HTML is missing/unparseable (caller falls back to the abstract).
    """
    parsed = parse_sections(arxiv_id)
    if parsed is None:
        return None
    abstract, sections = parsed
    if not abstract and not sections:
        return None

    by_bucket: dict[str, str] = {}
    for _title, bucket, text in sections:
        if bucket and bucket not in by_bucket:
            by_bucket[bucket] = text

    parts: list[str] = []
    if abstract:
        parts.append(f"ABSTRACT: {_first_chars(abstract, abstract_chars)}")
    intro = by_bucket.get("intro")
    if intro:
        head = _first_chars(intro, intro_chars // 2)
        tail = intro[-(intro_chars // 2) :] if len(intro) > intro_chars else ""
        contrib = head + (f" […] {tail}" if tail else "")
        parts.append(f"CONTRIBUTION: {contrib}")
    if "method" in by_bucket:
        parts.append(f"METHOD: {_first_chars(by_bucket['method'], method_chars)}")
    if "results" in by_bucket:
        parts.append(f"RESULTS: {_first_chars(by_bucket['results'], results_chars)}")
    return "\n".join(parts) if parts else None


def extract_full(arxiv_id: str, max_chars: int = 60000) -> str | None:
    """
    All body text (abstract + every section), for the full-context timing bench
    """
    parsed = parse_sections(arxiv_id)
    if parsed is None:
        return None
    abstract, sections = parsed
    chunks: list[str] = []
    if abstract:
        chunks.append(f"Abstract\n{abstract}")
    for title, _bucket, text in sections:
        chunks.append(f"{title}\n{text}")
    full = "\n\n".join(chunks)
    return full[:max_chars] if full else None
