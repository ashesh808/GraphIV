"""
Per-leaf community summaries over the topic tree, as an optional retrieval tier

It is resumable and idempotent, skipping any leaf already present in the database
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import httpx

from graphiv.preprocess._common import (
    COMMUNITY_SUMMARY_DB,
    LLM_BASE_URL,
    LLM_ROUTER,
    MAP_MODEL,
    OLD_SQLITE,
    SUMMARY_MODEL_TAG,
    TOPIC_TREE_DB,
)

_SYSTEM = (
    "You name research-paper clusters. Given a list of paper titles from one cluster, "
    "reply with a compact JSON object: "
    '{"label": "<=6-word topic name", "summary": "1-2 sentence description of what this '
    'cluster studies"}. No prose outside the JSON.'
)


def _model_listed(model: str) -> bool:
    """
    Health via /v1/models only (never a chat completion)
    """
    try:
        r = httpx.get(f"{LLM_BASE_URL}/models", timeout=10.0)
        if r.status_code != 200:
            return False
        data: dict[str, Any] = r.json()
        return any(m.get("id") == model for m in data.get("data", []))
    # a health probe treats every failure as unreachable, by design
    except Exception:  # noqa: BLE001
        return False


def _restart_router(model: str) -> None:
    """
    Restart the router and wait until `model` is listed again (recovery only)
    """
    print("  >>> /router/restart", flush=True)
    try:
        _ = httpx.get(f"{LLM_ROUTER}/router/restart", timeout=60.0)
    # a health probe treats every failure as unreachable, by design
    except Exception as e:  # noqa: BLE001
        print(f"      restart error: {e}", flush=True)
    for _ in range(60):
        if _model_listed(model):
            return
        time.sleep(2.0)
    print("      WARN: router did not list model after 120s", flush=True)


def _chat(titles: list[str]) -> dict[str, str] | None:
    """
    One labeling call; returns {'label','summary'} or None on parse/transport failure
    """
    if not _model_listed(MAP_MODEL):
        _restart_router(MAP_MODEL)
    user = "Titles:\n" + "\n".join(f"- {t}" for t in titles)
    body: dict[str, Any] = {
        "model": MAP_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 200,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    for attempt in range(3):
        try:
            r = httpx.post(f"{LLM_BASE_URL}/chat/completions", json=body, timeout=300.0)
            text: str = r.json()["choices"][0]["message"]["content"]
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end < 0:
                return None
            obj: dict[str, str] = json.loads(text[start : end + 1])
            return {
                "label": str(obj.get("label", "")),
                "summary": str(obj.get("summary", "")),
            }
        except Exception as e:  # noqa: BLE001
            if attempt >= 2:
                print(f"  [summary] final error: {type(e).__name__}", flush=True)
                return None
            _restart_router(MAP_MODEL)
    return None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS summary ("
        "leaf_id INT PRIMARY KEY, label TEXT, summary TEXT, "
        "n_papers INT, sample_ids TEXT, model TEXT)"
    )
    conn.commit()


def run_summaries(sample_per_leaf: int, limit: int | None) -> None:
    """
    Label each topic leaf with the map LLM; resumable, skips done leaves
    """
    if not TOPIC_TREE_DB.exists():
        raise SystemExit(f"[summary] topic tree missing: {TOPIC_TREE_DB} (build it first)")

    tree = sqlite3.connect(f"file:{TOPIC_TREE_DB}?mode=ro", uri=True)
    leaves: list[tuple[int, int]] = tree.execute(
        "SELECT leaf_id, size FROM leaf ORDER BY size DESC"
    ).fetchall()

    COMMUNITY_SUMMARY_DB.parent.mkdir(parents=True, exist_ok=True)
    out = sqlite3.connect(COMMUNITY_SUMMARY_DB)
    _ensure_schema(out)
    done: set[int] = {r[0] for r in out.execute("SELECT leaf_id FROM summary")}

    old = sqlite3.connect(f"file:{OLD_SQLITE}?mode=ro", uri=True)
    todo = [(lid, sz) for lid, sz in leaves if lid not in done]
    if limit:
        todo = todo[:limit]
    print(
        f"[summary] {len(leaves)} leaves, {len(done)} done, labeling {len(todo)}",
        flush=True,
    )

    t0 = time.time()
    for i, (lid, size) in enumerate(todo, 1):
        ids: list[str] = [
            r[0]
            for r in tree.execute(
                "SELECT arxiv_id FROM paper_topic WHERE leaf_id = ? LIMIT ?",
                (lid, sample_per_leaf),
            )
        ]
        if not ids:
            continue
        placeholders = ",".join("?" * len(ids))
        titles: list[str] = [
            r[0]
            for r in old.execute(f"SELECT title FROM publication WHERE id IN ({placeholders})", ids)
        ]
        result = _chat(titles)
        if result is None:
            continue
        _ = out.execute(
            "INSERT OR REPLACE INTO summary VALUES (?,?,?,?,?,?)",
            (
                lid,
                result["label"],
                result["summary"],
                size,
                ",".join(ids),
                SUMMARY_MODEL_TAG,
            ),
        )
        if i % 25 == 0:
            out.commit()
            rate = i / (time.time() - t0)
            print(f"[summary] {i}/{len(todo)}  {rate:.1f} leaf/s", flush=True)
    out.commit()
    out.close()
    tree.close()
    old.close()
    print(
        f"[summary] done in {time.time() - t0:.0f}s -> {COMMUNITY_SUMMARY_DB}",
        flush=True,
    )
