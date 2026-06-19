"""Gemma-4-26B teacher labeler for citation intent + polarity.

Reads `(citing_id, ordinal)` pairs from sample.txt, fetches `(section,
sentence)` from Postgres for each pair, batches them, sends to the local
llama.cpp server (OpenAI-compatible) and writes the parsed labels into
`data/citation_labels/labels.db` (SQLite).

Idempotent and resumable: at startup we read `labels.db` to skip any pair
that already has a row. Connection failures call `GET /router/restart`,
poll `/v1/models` until the model is back, and retry the same batch.

Best (parallelism, batch_size) from benchmarking: **P=4, BS=50** at ~8.2
citations/s, 98.5% valid labels. 100k labels ≈ 3.4 hours.

Run:  python -m phase_3.label.teacher
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import psycopg
from openai import AsyncOpenAI

from ._common import (
    ARXIVKG_PG_DSN,
    INTENTS,
    LABELS_DB,
    LABELS_DIR,
    POLARITIES,
    SAMPLE_TXT,
)

BASE_URL: str = "http://localhost:11434/v1"
ROUTER_BASE: str = "http://localhost:11434"
API_KEY: str = "none"
MODEL: str = "Gemma-4-26B"
MODEL_TAG: str = (
    "gemma-4-26b-v6"  # stored in labels.intent_model; bumped per prompt version
)

DEFAULT_PARALLELISM: int = 4
DEFAULT_BATCH_SIZE: int = 50

# v6 prompt selected after 6 iterations of triage on 100-citation samples;
# trajectory: v1 ~88% -> v6 ~98% label accuracy (subjective triage).
# See scratchpad/intent/prompts/v6.txt and scratchpad/intent/runs/iter_6.json.
PROMPT_PATH: Path = Path(__file__).resolve().parent / "system_prompt.txt"
SYSTEM_PROMPT: str = PROMPT_PATH.read_text(encoding="utf-8")


@dataclass
class Citation:
    citing_id: int
    ordinal: int
    section: str
    sentence: str


# ---------------------------------------------------------------------------
# SQLite labels store


SCHEMA_SQL: str = (
    "CREATE TABLE IF NOT EXISTS label ("
    "  citing_id INTEGER NOT NULL,"
    "  ordinal   INTEGER NOT NULL,"
    "  intent    TEXT,"
    "  polarity  TEXT,"
    "  model     TEXT NOT NULL,"
    "  ok        INTEGER NOT NULL,"  # 1 = parsed + in legal label set
    "  raw       TEXT,"  # raw label dict json, useful for debugging
    "  PRIMARY KEY (citing_id, ordinal)"
    ")"
)


def open_labels_db() -> sqlite3.Connection:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LABELS_DB)
    _ = conn.execute(SCHEMA_SQL)
    _ = conn.execute("PRAGMA journal_mode=WAL")
    _ = conn.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
    return conn


def already_labeled(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    rows: list[tuple[int, int]] = cast(
        list[tuple[int, int]],
        conn.execute("SELECT citing_id, ordinal FROM label").fetchall(),
    )
    return set(rows)


# ---------------------------------------------------------------------------
# Sample input


def load_sample(path: Path) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            a, b = line.split("\t")
            pairs.append((int(a), int(b)))
    return pairs


def fetch_payloads(
    pg: psycopg.Connection[tuple[object, ...]],
    pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], Citation]:
    """Fetch (section, sentence) for each (citing_id, ordinal). Chunked."""
    out: dict[tuple[int, int], Citation] = {}
    if not pairs:
        return out
    cur = pg.cursor()
    chunk_size = 5000
    for start in range(0, len(pairs), chunk_size):
        chunk = pairs[start : start + chunk_size]
        # Build a VALUES list for the join filter
        values_sql = ",".join("(%s,%s)" for _ in chunk)
        params: list[int] = []
        for cid, ord_ in chunk:
            params.append(cid)
            params.append(ord_)
        sql = (
            "SELECT c.citing_id, c.ordinal, COALESCE(c.section,''), c.sentence "
            f"FROM citation c JOIN (VALUES {values_sql}) AS v(cid, ord) "
            "ON c.citing_id = v.cid AND c.ordinal = v.ord "
            "WHERE c.sentence IS NOT NULL"
        )
        _ = cur.execute(sql, params)
        rows: list[tuple[int, int, str, str]] = cast(
            list[tuple[int, int, str, str]], cur.fetchall()
        )
        for cid, ord_, section, sentence in rows:
            out[(cid, ord_)] = Citation(
                citing_id=cid, ordinal=ord_, section=section, sentence=sentence
            )
    return out


# ---------------------------------------------------------------------------
# LLM call + restart-on-failure


_RESTART_LOCK: asyncio.Lock = asyncio.Lock()
_RESTART_GEN: int = 0


async def _models_status() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as h:
            r = await h.get(f"{BASE_URL}/models")
            if r.status_code != 200:
                return {}
            data = r.json()
            return {
                m["id"]: m.get("status", {}).get("value", "?")
                for m in data.get("data", [])
            }
    except Exception:
        return {}


async def restart_server() -> None:
    global _RESTART_GEN
    async with _RESTART_LOCK:
        gen_before = _RESTART_GEN
        print("  >>> calling /router/restart", flush=True)
        try:
            async with httpx.AsyncClient(timeout=60.0) as h:
                r = await h.get(f"{ROUTER_BASE}/router/restart")
                print(f"      restart -> {r.status_code} {r.text[:120]}", flush=True)
        except Exception as e:
            print(f"      restart error: {e}", flush=True)
        for attempt in range(60):
            status = await _models_status()
            if MODEL in status:
                print(
                    f"      server reachable after {attempt + 1} probe(s) status={status.get(MODEL)}",
                    flush=True,
                )
                _RESTART_GEN = gen_before + 1
                return
            await asyncio.sleep(2.0)
        print("      WARN: server did not come back after 120s", flush=True)
        _RESTART_GEN = gen_before + 1


def build_user_msg(batch: list[Citation]) -> str:
    parts: list[str] = ["Label these citations:\n"]
    for i, c in enumerate(batch):
        sect = c.section or "(unknown)"
        sect = re.sub(r"^[\d\.]+\s*", "", sect)[:60]
        parts.append(f'[{i}] section="{sect}" | "{c.sentence}"')
    return "\n".join(parts)


def parse_labels(content: str) -> list[dict[str, Any]]:
    """Strip markdown fences, parse JSON, return list of label dicts."""
    s = content.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        obj = json.loads(s)
    except Exception:
        return []
    if isinstance(obj, dict) and "labels" in obj:
        labels = obj["labels"]
    else:
        labels = obj
    if not isinstance(labels, list):
        return []
    return [x for x in labels if isinstance(x, dict)]


async def label_batch(
    client: AsyncOpenAI,
    batch: list[Citation],
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    user_msg = build_user_msg(batch)
    for attempt in range(max_retries + 1):
        gen_at_call = _RESTART_GEN
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=max(400, 40 * len(batch)),
                timeout=1200,
            )
            content = resp.choices[0].message.content or ""
            return parse_labels(content)
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:160]}"
            is_conn = (
                "Could not establish connection" in msg
                or "ConnectError" in msg
                or "InternalServerError" in msg
            )
            if not is_conn or attempt >= max_retries:
                print(f"    request error (final): {msg}", flush=True)
                return []
            print(f"    request error (attempt {attempt + 1}): {msg}", flush=True)
            if _RESTART_GEN == gen_at_call:
                await restart_server()
            else:
                await asyncio.sleep(1.0)
    return []


# ---------------------------------------------------------------------------
# Driver


async def run(
    parallelism: int,
    batch_size: int,
    sample_path: Path,
) -> None:
    print(f"phase_3.label.teacher  P={parallelism} BS={batch_size}", flush=True)
    sample = load_sample(sample_path)
    print(f"  sample.txt: {len(sample):,} pairs", flush=True)

    lconn = open_labels_db()
    done = already_labeled(lconn)
    print(f"  already labeled: {len(done):,} pairs", flush=True)

    todo = [p for p in sample if p not in done]
    print(f"  to label: {len(todo):,} pairs", flush=True)
    if not todo:
        lconn.close()
        return

    print("  connecting to Postgres ...", flush=True)
    pg = psycopg.connect(ARXIVKG_PG_DSN)
    print("  fetching payloads ...", flush=True)
    t0 = time.time()
    payloads = fetch_payloads(pg, todo)
    pg.close()
    print(f"    payloads: {len(payloads):,} in {time.time() - t0:.1f}s", flush=True)
    # filter todo to only pairs that actually have a payload
    work: list[Citation] = [payloads[p] for p in todo if p in payloads]
    skipped = len(todo) - len(work)
    if skipped:
        print(
            f"  WARN: {skipped} pairs had no payload (likely deleted/null sentence)",
            flush=True,
        )

    # cold restart so we begin from a known state
    await restart_server()

    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    # warmup
    try:
        _ = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hello!"}],
            max_tokens=5,
            timeout=600,
        )
    except Exception as e:
        print(f"  warmup error: {e}", flush=True)

    sem = asyncio.Semaphore(parallelism)
    batches: list[list[Citation]] = [
        work[i : i + batch_size] for i in range(0, len(work), batch_size)
    ]
    total_batches = len(batches)
    n_done = 0
    n_valid = 0
    n_seen = 0
    t_start = time.time()
    # buffer writes to SQLite to amortize commit cost
    write_buf: list[tuple[int, int, str | None, str | None, str, int, str]] = []
    buf_lock = asyncio.Lock()
    last_flush = time.time()

    async def flush_buf() -> None:
        nonlocal write_buf
        if not write_buf:
            return
        async with buf_lock:
            rows = write_buf
            write_buf = []
        _ = lconn.executemany(
            "INSERT OR IGNORE INTO label "
            "(citing_id, ordinal, intent, polarity, model, ok, raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        lconn.commit()

    async def runner(b: list[Citation]) -> None:
        nonlocal n_done, n_valid, n_seen, last_flush
        async with sem:
            labels = await label_batch(client, b)
        rows_to_write: list[tuple[int, int, str | None, str | None, str, int, str]] = []
        for i, c in enumerate(b):
            lab = labels[i] if i < len(labels) and isinstance(labels[i], dict) else {}
            intent = lab.get("intent") if isinstance(lab.get("intent"), str) else None
            polarity = (
                lab.get("polarity") if isinstance(lab.get("polarity"), str) else None
            )
            ok = int(intent in INTENTS and polarity in POLARITIES)
            raw = json.dumps(lab) if lab else "{}"
            rows_to_write.append(
                (c.citing_id, c.ordinal, intent, polarity, MODEL_TAG, ok, raw)
            )
        async with buf_lock:
            write_buf.extend(rows_to_write)
            n_done += 1
            n_seen += len(b)
            n_valid += sum(r[5] for r in rows_to_write)
        # periodic flush + progress print
        if time.time() - last_flush > 10.0:
            await flush_buf()
            last_flush = time.time()
            elapsed = time.time() - t_start
            rate = n_seen / elapsed if elapsed > 0 else 0
            eta = (len(work) - n_seen) / rate if rate > 0 else 0
            print(
                f"  [{n_done}/{total_batches}]  {n_seen:>7,}/{len(work):,} "
                f"({n_seen / len(work):.1%})  {rate:.2f} cit/s  valid={n_valid / max(1, n_seen):.2%}  "
                f"eta={eta / 60:.1f} min",
                flush=True,
            )

    await asyncio.gather(*[runner(b) for b in batches])
    await flush_buf()

    elapsed = time.time() - t_start
    print(
        f"\nDONE. {n_seen:,} citations in {elapsed / 60:.1f} min "
        f"({n_seen / elapsed:.2f} cit/s, valid={n_valid / max(1, n_seen):.2%})",
        flush=True,
    )
    lconn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemma teacher labeler")
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--parallelism", type=int, default=DEFAULT_PARALLELISM
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--sample", type=str, default=str(SAMPLE_TXT), help="Path to sample.txt"
    )
    args = parser.parse_args()
    parallelism: int = args.parallelism  # pyright: ignore[reportAny]
    batch_size: int = args.batch_size  # pyright: ignore[reportAny]
    sample_path: str = args.sample  # pyright: ignore[reportAny]
    asyncio.run(run(parallelism, batch_size, Path(sample_path)))
