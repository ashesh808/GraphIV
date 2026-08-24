"""
Router plumbing every LLM role shares: date preamble, health probe, restart

Health is read from /v1/models and never from a chat completion, which would evict GPU work
The restart is recovery only, so nothing cold-starts the router at import
"""

from __future__ import annotations

import asyncio

import httpx

from graphiv.core.settings import LLM_BASE_URL, LLM_ROUTER


def dated(system: str) -> str:
    """
    Prefix a system prompt with today's date, models otherwise treat post-cutoff years

        (e.g. real 2026 arXiv ids) as implausible and flag them as hallucinations.
    """
    from datetime import date

    today = date.today()
    return (
        f"Today is {today.year}-{today.month:02d}. arXiv ids and publication years "
        f"through {today.year} are valid and real.\n\n{system}"
    )


async def model_status(model: str) -> str | None:
    """
    Return the router's status string for `model`, or None if unreachable/absent

        Health via /v1/models only, never a chat completion (memory: llm-health-check).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as h:
            r = await h.get(f"{LLM_BASE_URL}/models")
            if r.status_code != 200:
                return None
            data = r.json()
            for m in data.get("data", []):
                if m.get("id") == model:
                    return m.get("status", {}).get("value", "?")
    # a health probe treats every failure as unreachable, by design
    except Exception:  # noqa: BLE001
        return None
    return None


async def restart_router(model: str) -> None:
    """
    Restart the router and wait until `model` is listed again (recovery only)
    """
    print("  >>> /router/restart", flush=True)
    try:
        async with httpx.AsyncClient(timeout=60.0) as h:
            r = await h.get(f"{LLM_ROUTER}/router/restart")
            print(f"      restart -> {r.status_code}", flush=True)
    # a health probe treats every failure as unreachable, by design
    except Exception as e:  # noqa: BLE001
        print(f"      restart error: {e}", flush=True)
    for _ in range(60):
        if await model_status(model) is not None:
            return
        await asyncio.sleep(2.0)
    print("      WARN: router did not list model after 120s", flush=True)
