"""
Is a sentence in a report supported by the paper it cites

Evidence is retrieved from the cited paper, never read from its opening alone
A sentence citing several papers passes when any one of them supports it
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .._boot import SQLITE_DB
from .._llm import chat

WORKERS = 8
TOP_K = 8
_LOCK = threading.Lock()

_ID = r"\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7}"
_CITE = re.compile(rf"\[arXiv:({_ID})\]", re.IGNORECASE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[a-z][a-z0-9\-]{3,}")
_STOP = frozenset(
    "this that these those with from have been which their there where when what were also "
    "such using used than then they them into more most other some both each only over "
    "paper work approach method model models results show shows however while".split()
)

SUPPORT_SYS = (
    "You check one citation in a literature review. You get a CLAIM and text from the paper it "
    "cites. Decide whether that paper supports the claim.\n"
    "yes = the paper clearly supports it. partial = related but the paper does not state this. "
    "no = the paper is about something else, or contradicts it.\n"
    "Answer ONE word: yes, partial, or no."
)


def _words(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP}


def open_cache(path: Path) -> sqlite3.Connection:
    """
    The verdict cache, shared by the worker pool so every use of it holds the module lock

    Args:
        path: Where the sqlite file lives.

    Returns:
        An open connection with the table present.
    """
    conn = sqlite3.connect(path, timeout=60, check_same_thread=False)
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS v ("
        "key TEXT PRIMARY KEY, report TEXT, judge TEXT, task TEXT, aid TEXT, verdict TEXT)"
    )
    conn.commit()
    return conn


def key(*parts: str) -> str:
    """
    A cache key over any tuple of strings
    """
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def sentences(report: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """
    Split a report into sentences, keeping the ids each one cites

    Table rows, headings and the run footer are dropped, since none of them is a claim.

    Args:
        report: The report markdown.

    Returns:
        (rows of (clean sentence, cited ids), the cited sentences as plain text).
    """
    body = [
        ln
        for ln in report.splitlines()
        if ln.strip()
        and not ln.startswith(("|", "#", ">", "- [", "![", "---", "*deep research", "["))
        and "graph.html" not in ln
    ]
    rows: list[tuple[str, list[str]]] = []
    for raw in _SENT.split("\n".join(body)):
        ids = sorted({m.group(1).lower() for m in _CITE.finditer(raw)})
        clean = _WS.sub(" ", re.sub(r"\(https?://\S+\)", "", _CITE.sub("", raw))).strip()
        if len(clean) > 40:
            rows.append((clean, ids))
    return rows, [c for c, ids in rows if ids]


def paper_text(aid: str, html_dir: Path) -> list[str]:
    """
    The cited paper's own sentences, from the local LaTeXML render

    Args:
        aid: The arxiv id.
        html_dir: The root of the HTML store.

    Returns:
        Sentences, empty when the paper has no local render.
    """
    stem, yymm = (aid.replace("/", ""), aid.split("/", 1)[1][:4]) if "/" in aid else (aid, aid[:4])
    p = html_dir / yymm / f"{stem}.html"
    if not p.is_file():
        return []
    raw = re.sub(r"(?is)<(script|style|math)\b.*?</\1>", " ", p.read_text(errors="replace"))
    txt = _WS.sub(" ", _TAG.sub(" ", raw)).strip()
    return [s.strip() for s in _SENT.split(txt) if 60 < len(s.strip()) < 600]


def evidence(claim: str, aid: str, html_dir: Path, cache: dict[str, list[str]]) -> str | None:
    """
    The paper's opening plus the sentences in it sharing the most words with the claim

    Retrieval by word overlap keeps the GPU free for the judge, which does the reasoning.

    Args:
        claim: The sentence being checked.
        aid: The cited paper.
        html_dir: The root of the HTML store.
        cache: Per-paper sentence lists, filled in place.

    Returns:
        Evidence text, or None when the paper has no local render.
    """
    if aid not in cache:
        cache[aid] = paper_text(aid, html_dir)
    sents = cache[aid]
    if not sents:
        return None
    cw = _words(claim)
    top = sorted(sents, key=lambda s: -len(cw & _words(s)))[:TOP_K]
    body = [x for x in sents if "@" not in x and x.count(",") < 8]
    head = " ".join(body[:6])
    return f"OPENING:\n{head[:3000]}\n\nMOST RELEVANT PASSAGES:\n" + "\n".join(
        f"- {s}" for s in top
    )


def ask(claim: str, ev: str | None, judge: str) -> str:
    """
    One support verdict from the named judge

    Args:
        claim: The sentence from the report.
        ev: The cited paper's evidence, or None when it has none.
        judge: The router model name.

    Returns:
        One of yes, partial, no, or skip.
    """
    if ev is None:
        return "skip"
    a = chat(judge, SUPPORT_SYS, f"CLAIM: {claim}\n\nCITED PAPER TEXT:\n{ev}", 0.0, 2000)
    a = a.strip().lower()
    return "yes" if "yes" in a else "partial" if "partial" in a else "no"


def cached_ask(
    conn: sqlite3.Connection,
    report: str,
    judge: str,
    task: str,
    claim: str,
    aid: str,
    html_dir: Path,
    cache: dict[str, list[str]],
) -> str:
    """
    A support verdict, read from the cache when it is already there

    Args:
        conn: The verdict cache.
        report: The report identifier.
        judge: The router model name.
        task: Either support or planted, which keeps the two arms apart.
        claim: The sentence being checked.
        aid: The paper it is checked against.
        html_dir: The root of the HTML store.
        cache: Per-paper sentence lists, filled in place.

    Returns:
        One of yes, partial, no, or skip.
    """
    k = key(report, judge, task, claim, aid)
    with _LOCK:
        row = conn.execute("SELECT verdict FROM v WHERE key=?", (k,)).fetchone()
    if row:
        return row[0]
    v = ask(claim, evidence(claim, aid, html_dir, cache), judge)
    with _LOCK:
        _ = conn.execute(
            "INSERT OR REPLACE INTO v VALUES (?,?,?,?,?,?)", (k, report, judge, task, aid, v)
        )
    return v


def census(
    report_path: Path, judge: str, conn: sqlite3.Connection, html_dir: Path
) -> dict[str, int]:
    """
    Score every citing sentence in one report, passing it when any cited paper supports it

    Args:
        report_path: Path to report.md.
        judge: The router model name.
        conn: The verdict cache.
        html_dir: The root of the HTML store.

    Returns:
        Sentence counts plus one count per verdict.
    """
    name = f"{report_path.parent.parent.name}/{report_path.parent.name}"
    rows, _ = sentences(report_path.read_text())
    cited = [(s, ids) for s, ids in rows if ids]
    cache: dict[str, list[str]] = {}

    def one(t: tuple[str, list[str]]) -> str:
        """
        Best verdict over the papers a sentence cites, where skip needs every one uncheckable
        """
        sent, ids = t
        got = {cached_ask(conn, name, judge, "support", sent, aid, html_dir, cache) for aid in ids}
        for v in ("yes", "partial", "no"):
            if v in got:
                return v
        return "skip"

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        got = list(ex.map(one, cited))
    conn.commit()
    out = {"sentences": len(rows), "cited": len(cited), "uncited": len(rows) - len(cited)}
    for v in ("yes", "partial", "no", "skip"):
        out[f"cited_{v}"] = got.count(v)
    return out


def coverage(report: str) -> dict[str, int]:
    """
    How many sentences carry a citation, counted without a model

    Args:
        report: The report markdown.

    Returns:
        Sentence, cited and uncited counts.
    """
    rows, cited = sentences(report)
    return {"sentences": len(rows), "cited": len(cited), "uncited": len(rows) - len(cited)}


__all__ = [
    "SQLITE_DB",
    "cached_ask",
    "census",
    "coverage",
    "evidence",
    "key",
    "open_cache",
    "paper_text",
    "sentences",
]
