"""P2 / R2 — fill the extraction schema from each paper's full text, concurrently.

Map stage: for each landmark, read its ar5iv full text (fulltext.extract_salient) and ask
the thinking-off Gemma-4-26B to fill the schema fields as JSON. Cached by (arxiv_id,
schema_hash) so re-runs and shared landmarks are free. Abstract fallback when HTML is missing.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

from openai import AsyncOpenAI


from _common import DATA_DIR, LLM_BASE_URL  # noqa: E402
from fulltext import extract_salient  # noqa: E402
from narrate import model_status, restart_router  # noqa: E402
from schema import Schema  # noqa: E402

MAP_MODEL = "Gemma-4-26B"
CONCURRENCY = 4
CACHE_DB = DATA_DIR / "metadata" / "extract_cache.db"
_NO_THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": False}}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS extraction "
        "(arxiv_id TEXT, schema_hash TEXT, json TEXT, model TEXT, "
        "PRIMARY KEY (arxiv_id, schema_hash))"
    )
    return conn


def _cached(ids: list[str], shash: str) -> dict[str, dict[str, str]]:
    if not ids:
        return {}
    conn = _conn()
    q = (
        "SELECT arxiv_id, json FROM extraction WHERE schema_hash=? AND arxiv_id IN (%s)"
        % (",".join("?" * len(ids)))
    )
    rows: list[tuple[str, str]] = conn.execute(q, [shash, *ids]).fetchall()
    conn.close()
    out: dict[str, dict[str, str]] = {}
    for aid, js in rows:
        try:
            out[aid] = json.loads(js)
        except Exception:  # noqa: BLE001
            pass
    return out


def _sys_prompt(schema: Schema) -> str:
    fields = "\n".join(f"  {n}: {d}" for n, d in schema.fields)
    return (
        "Extract these fields from the paper text. Be specific and factual; cite numbers "
        'when present. Use "n/a" if a field is not addressed. Do NOT show reasoning.\n'
        f"FIELDS:\n{fields}\n"
        'Output ONLY JSON: {"<field>": "<short value>", ...}.'
    )


async def _one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    aid: str,
    title: str,
    schema: Schema,
    fallback: str,
) -> tuple[str, dict[str, str] | None]:
    async with sem:
        snip = extract_salient(aid) or fallback
        if not snip:
            return aid, None
        try:
            resp = await client.chat.completions.create(
                model=MAP_MODEL,
                messages=[
                    {"role": "system", "content": _sys_prompt(schema)},
                    {"role": "user", "content": f"Title: {title}\n\n{snip}"},
                ],
                temperature=0.2,
                max_tokens=600,
                timeout=600,
                extra_body=_NO_THINK,
            )
        except Exception:  # noqa: BLE001
            return aid, None
        obj = _parse(resp.choices[0].message.content or "")
        return aid, obj


def _parse(text: str) -> dict[str, str] | None:
    from llm import parse_json

    obj = parse_json(text)
    if not isinstance(obj, dict):
        return None
    return {str(k): str(v)[:300] for k, v in obj.items()}  # pyright: ignore[reportAny]


async def extract_many(
    items: list[tuple[str, str]], schema: Schema, fallbacks: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Fill `schema` for each (arxiv_id, title), using+filling the cache. id -> {field:val}."""
    have = _cached([a for a, _ in items], schema.hash)
    todo = [(a, t) for a, t in items if a not in have]
    if not todo:
        return have
    if await model_status(MAP_MODEL) is None:
        await restart_router(MAP_MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        results = await asyncio.gather(
            *[_one(client, sem, a, t, schema, fallbacks.get(a, "")) for a, t in todo]
        )
    conn = _conn()
    for aid, obj in results:
        if obj:
            have[aid] = obj
            _ = conn.execute(
                "INSERT OR REPLACE INTO extraction VALUES (?,?,?,?)",
                (aid, schema.hash, json.dumps(obj), MAP_MODEL),
            )
    conn.commit()
    conn.close()
    return have
