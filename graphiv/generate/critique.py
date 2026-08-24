"""
Per-paper deep critique from the full PDF, for the deepest research tiers

Novelty, strengths, weaknesses and limitations are read out of the paper rather than the abstract
This is the depth lever, and its cost scales with critique_k
"""

from __future__ import annotations

import asyncio
import sqlite3

from graphiv.core.llm import THINK, chat
from graphiv.core.router import model_status, restart_router
from graphiv.core.settings import DATA_DIR
from graphiv.generate.fulltext import extract_full
from graphiv.generate.pdf_figures import pdf_text

CRIT_MODEL = "Gemma-4-26B"
CONCURRENCY = 2  # full-paper + thinking on Gemma-4-26B is VRAM-heavy; keep the 3090 calm
CACHE_DB = DATA_DIR / "metadata" / "critique_cache.db"

_SYS = (
    "You are a critical peer reviewer. Read the paper's full text and write a TIGHT critique "
    "for a literature review, grounded only in the text. Cover, in 4 short labeled lines:\n"
    "NOVELTY: what is genuinely new.\n"
    "STRENGTHS: the strongest evidence/result (cite a number if present).\n"
    "WEAKNESSES: the most important limitation or unsupported claim.\n"
    "RELEVANCE: how it advances the review's question.\n"
    "Be specific and skeptical; do not pad. No preamble."
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS critique "
        "(arxiv_id TEXT PRIMARY KEY, question_hash TEXT, text TEXT, model TEXT)"
    )
    return conn


def _cached(ids: list[str], qhash: str) -> dict[str, str]:
    if not ids:
        return {}
    conn = _conn()
    placeholders = ",".join("?" * len(ids))
    q = (
        "SELECT arxiv_id, text FROM critique "
        f"WHERE question_hash=? AND arxiv_id IN ({placeholders})"
    )
    rows: list[tuple[str, str]] = conn.execute(q, [qhash, *ids]).fetchall()
    conn.close()
    return {aid: txt for aid, txt in rows}


async def _one(
    sem: asyncio.Semaphore, aid: str, title: str, year: int | None, question: str
) -> tuple[str, str | None]:
    async with sem:
        body = pdf_text(aid) or extract_full(aid)
        if not body:
            return aid, None
        yr = year if year is not None else "?"
        user = (
            f"Review question: {question}\n"
            f"Paper arXiv:{aid} ({yr}) — {title}\n\nFULL TEXT (may be truncated):\n{body}"
        )
        try:
            text, _, _ = await chat(CRIT_MODEL, _SYS, user, 0.3, 1200, extra_body=THINK)
        except Exception:  # noqa: BLE001
            return aid, None
        return aid, text.strip() or None


async def critique_many(
    items: list[tuple[str, str, int | None]], question: str, qhash: str
) -> dict[str, str]:
    """
    Critique each (arxiv_id, title, year), using+filling the cache. id -> critique text
    """
    have = _cached([a for a, _, _ in items], qhash)
    todo = [(a, t, y) for a, t, y in items if a not in have]
    if not todo:
        return have
    if await model_status(CRIT_MODEL) is None:
        await restart_router(CRIT_MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*[_one(sem, a, t, y, question) for a, t, y in todo])
    conn = _conn()
    for aid, txt in results:
        if txt:
            have[aid] = txt
            _ = conn.execute(
                "INSERT OR REPLACE INTO critique VALUES (?,?,?,?)",
                (aid, qhash, txt, CRIT_MODEL),
            )
    conn.commit()
    conn.close()
    return have
