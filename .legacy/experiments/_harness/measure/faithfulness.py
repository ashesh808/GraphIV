"""
The faithfulness tripwire: does the cited paper actually support the claim

It samples sentences citing exactly one id and asks the judge, scoring partial as a half
Its value is catching a mis-attribution bug, not ranking levers, since every arm scores high
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .._boot import JUDGE_MODEL, SQLITE_DB
from .._llm import chat

_ARXIV = re.compile(r"arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5})", re.IGNORECASE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*\-])")

_SYS = (
    "You verify a citation. Given a CLAIM sentence and the TITLE+ABSTRACT of the cited paper, "
    "decide whether that paper actually supports the claim. Answer ONE word: yes / partial / no."
)


def _single_cite_sentences(report: str, limit: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for sent in _SENT.split(report):
        ids = _ARXIV.findall(sent)
        if len(ids) == 1 and len(sent) < 600:
            out.append((sent.strip(), ids[0].lower()))
        if len(out) >= limit * 3:
            break
    # spread the sample across the report
    step = max(1, len(out) // max(1, limit))
    return out[::step][:limit]


def _abstract(conn: sqlite3.Connection, aid: str) -> tuple[str, str] | None:
    cur = conn.execute("SELECT title, abstract FROM publication WHERE lower(id)=?", (aid,))
    row: tuple[str, str] | None = cur.fetchone()
    return row


def faithfulness(report: str, k: int = 8) -> dict[str, Any]:
    """
    Sample k single-cite claims and judge support

    Returns sampled/faithfulness/verdicts.
    """
    pairs = _single_cite_sentences(report, k)
    conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    verdicts: list[dict[str, str]] = []
    yes = partial = sampled = 0
    try:
        for sent, aid in pairs:
            row = _abstract(conn, aid)
            if row is None:
                verdicts.append({"id": aid, "verdict": "skip"})
                continue
            title, abstract = row
            user = f"CLAIM: {sent}\n\nCITED PAPER:\nTITLE: {title}\nABSTRACT: {abstract[:1500]}"
            ans = chat(JUDGE_MODEL, _SYS, user, temperature=0.0, max_tokens=8).strip().lower()
            v = "yes" if "yes" in ans else "partial" if "partial" in ans else "no"
            verdicts.append({"id": aid, "verdict": v})
            sampled += 1
            yes += v == "yes"
            partial += v == "partial"
    finally:
        conn.close()
    score = (yes + 0.5 * partial) / sampled if sampled else 0.0
    return {"sampled": sampled, "faithfulness": round(score, 3), "verdicts": verdicts}
