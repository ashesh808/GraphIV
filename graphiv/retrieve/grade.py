"""
The reader pass: a role and a relevance grade for every landmark candidate

Fusing cosine with the grade is what keeps a high-in-degree but unrelated hub out of the cohort
A paper graded -2 leaves the landmark set but stays in the pool as a graph connector
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from openai import AsyncOpenAI

from graphiv.core.models import PoolNode
from graphiv.core.router import dated, model_status, restart_router
from graphiv.core.settings import DATA_DIR, LLM_BASE_URL, MAP_MODEL

CONCURRENCY = 4
CACHE_DB = DATA_DIR / "metadata" / "grade_cache.db"
LABELS = ("foundational", "core", "frontier", "adjacent", "survey", "unrelated")
_NO_THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": False}}

_SYS = (
    "You grade ONE research paper for a focused literature review answering a QUESTION. "
    "You see the paper's title, year, and abstract. Assign exactly one role:\n"
    "- foundational: seminal/origin work the question's methods are built upon; introduced a "
    "primitive the field now assumes.\n"
    "- core: a central, widely-built-on method or result in the question's main line "
    "(load-bearing, but not the origin).\n"
    "- frontier: recent work pushing the question's leading edge, new capabilities, SOTA, or "
    "open directions.\n"
    "- adjacent: genuinely related but tangential, an adjacent-domain application or a "
    "neighbouring lineage the review would only mention in passing.\n"
    "- survey: a survey/benchmark/tooling paper overviewing the question's area.\n"
    "- unrelated: off-topic for THIS question; a retrieval error that does not belong.\n"
    "Also grade relevance -2..2: 2 = must cover, 1 = worth covering, 0 = borderline, "
    "-1 = probably out, -2 = certainly out. `unrelated` MUST get -2. Judge by CONTENT vs the "
    "question, never by fame; use the year only as a recency hint.\n"
    'Output ONLY JSON: {"role":"<label>","relevance":N,"reason":"<=160 chars"}.'
)


@dataclass
class Grade:
    """
    One reader verdict: a role, a relevance in -2..2 and the reason
    """

    role: str
    relevance: int
    reason: str


def norm_rel(relevance: int) -> float:
    """
    Relevance -2..2 -> [0,1] fusion multiplier (a -2 paper zeroes out)
    """
    return (max(-2, min(2, relevance)) + 2) / 4.0


def fused_score(cosine: float, grade: Grade | None) -> float:
    """
    Cosine x norm(rel); ungraded papers get the neutral rel=0 multiplier
    """
    return cosine * (norm_rel(grade.relevance) if grade is not None else 0.5)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS grade "
        "(qhash TEXT, arxiv_id TEXT, role TEXT, relevance INTEGER, reason TEXT, "
        "model TEXT, PRIMARY KEY (qhash, arxiv_id))"
    )
    return conn


def _cached(qhash: str, ids: list[str]) -> dict[str, Grade]:
    if not ids:
        return {}
    conn = _conn()
    placeholders = ",".join("?" * len(ids))
    q = (
        "SELECT arxiv_id, role, relevance, reason FROM grade "
        f"WHERE qhash=? AND arxiv_id IN ({placeholders})"
    )
    rows: list[tuple[str, str, int, str]] = conn.execute(q, [qhash, *ids]).fetchall()
    conn.close()
    return {aid: Grade(role, int(rel), reason) for aid, role, rel, reason in rows}


def _parse(text: str) -> Grade | None:
    from graphiv.core.llm import parse_json

    obj = parse_json(text)
    if not isinstance(obj, dict):
        return None
    role = str(obj.get("role", "")).strip().lower()  # pyright: ignore[reportAny]
    if role not in LABELS:
        return None
    try:
        rel = max(-2, min(2, int(obj.get("relevance", 0))))  # pyright: ignore[reportAny]
    except Exception:  # noqa: BLE001
        rel = 0
    if role == "unrelated":
        rel = -2
    reason = str(obj.get("reason", ""))[:160]  # pyright: ignore[reportAny]
    return Grade(role, rel, reason)


async def _one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    question: str,
    node: PoolNode,
    abstract: str,
) -> tuple[str, Grade | None]:
    user = (
        f"QUESTION: {question}\n\nPAPER\ntitle: {node.title}\n"
        f"year: {node.year if node.year is not None else '?'}\n"
        f"arXiv: {node.arxiv_id}\nabstract: {abstract[:1500] or '(abstract unavailable)'}"
    )
    async with sem:
        for _ in range(2):  # one retry on an off-menu / unparseable label
            try:
                resp = await client.chat.completions.create(
                    model=MAP_MODEL,
                    messages=[
                        {"role": "system", "content": dated(_SYS)},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.0,
                    max_tokens=200,
                    timeout=600,
                    extra_body=_NO_THINK,
                )
            except Exception:  # noqa: BLE001
                return node.arxiv_id, None
            g = _parse(resp.choices[0].message.content or "")
            if g is not None:
                return node.arxiv_id, g
    return node.arxiv_id, None


def candidates(pool: dict[str, PoolNode], in_degree: dict[str, int], m: int) -> list[str]:
    """
    Grading set: top 2m by cosine UNION top 2m by in-pool in-degree

        The in-degree side catches ancestor-injected hubs (high fame, ~0.35 cosine) that would
        miss a pure-cosine cut yet are exactly the papers ranking will otherwise promote.
    """
    k = 2 * m
    by_cos = sorted(pool.values(), key=lambda n: -n.score)[:k]
    by_deg = sorted(pool.values(), key=lambda n: -in_degree.get(n.arxiv_id, 0))[:k]
    out: list[str] = []
    seen: set[str] = set()
    for n in [*by_cos, *by_deg]:
        if n.arxiv_id not in seen:
            seen.add(n.arxiv_id)
            out.append(n.arxiv_id)
    return out


_SUM_SYS = (
    "Summarize this research paper in 2-3 plain sentences: the problem, the method, and the "
    "headline result (with numbers when present). Factual, no hype, no preamble."
)


def _cached_summaries(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    conn = _conn()
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS summary "
        "(arxiv_id TEXT PRIMARY KEY, summary TEXT, model TEXT)"
    )
    placeholders = ",".join("?" * len(ids))
    q = f"SELECT arxiv_id, summary FROM summary WHERE arxiv_id IN ({placeholders})"
    rows: list[tuple[str, str]] = conn.execute(q, ids).fetchall()
    conn.close()
    return dict(rows)


async def _summarize_one(
    client: AsyncOpenAI, sem: asyncio.Semaphore, aid: str, title: str, abstract: str
) -> tuple[str, str | None]:
    if not abstract.strip():
        return aid, None
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=MAP_MODEL,
                messages=[
                    {"role": "system", "content": dated(_SUM_SYS)},
                    {"role": "user", "content": f"Title: {title}\n\n{abstract[:2500]}"},
                ],
                temperature=0.2,
                max_tokens=220,
                timeout=600,
                extra_body=_NO_THINK,
            )
        except Exception:  # noqa: BLE001
            return aid, None
        text = " ".join((resp.choices[0].message.content or "").split()).strip()
        return aid, text or None


async def summarize_many(items: list[tuple[str, str]], abstracts: dict[str, str]) -> dict[str, str]:
    """
    Question-agnostic 2-3 sentence summary per (arxiv_id, title); cached by arxiv_id
    """
    have = _cached_summaries([a for a, _ in items])
    todo = [(a, t) for a, t in items if a not in have]
    if not todo:
        return have
    if await model_status(MAP_MODEL) is None:
        await restart_router(MAP_MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        results = await asyncio.gather(
            *[_summarize_one(client, sem, a, t, abstracts.get(a, "")) for a, t in todo]
        )
    conn = _conn()
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS summary "
        "(arxiv_id TEXT PRIMARY KEY, summary TEXT, model TEXT)"
    )
    for aid, s in results:
        if s:
            have[aid] = s
            _ = conn.execute("INSERT OR REPLACE INTO summary VALUES (?,?,?)", (aid, s, MAP_MODEL))
    conn.commit()
    conn.close()
    return have


async def grade_many(
    question: str,
    qhash: str,
    pool: dict[str, PoolNode],
    ids: list[str],
    abstracts: dict[str, str],
) -> dict[str, Grade]:
    """
    Grade `ids` (cache-first) against `question`

    Returns id -> Grade.
    """
    have = _cached(qhash, ids)
    todo = [i for i in ids if i not in have and i in pool]
    if not todo:
        return have
    if await model_status(MAP_MODEL) is None:
        await restart_router(MAP_MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        results = await asyncio.gather(
            *[_one(client, sem, question, pool[i], abstracts.get(i, "")) for i in todo]
        )
    conn = _conn()
    for aid, g in results:
        if g is not None:
            have[aid] = g
            _ = conn.execute(
                "INSERT OR REPLACE INTO grade VALUES (?,?,?,?,?,?)",
                (qhash, aid, g.role, g.relevance, g.reason, MAP_MODEL),
            )
    conn.commit()
    conn.close()
    return have
