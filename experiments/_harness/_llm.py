"""
Minimal sync chat against the router, for the judge and faithfulness instruments

It imports nothing from the system under test, which keeps the instruments decoupled
Recovery is a router restart on a connection error, never a retry loop
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from ._boot import LLM_BASE_URL, LLM_ROUTER

_NO_THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": False}}


async def _chat_async(
    model: str, system: str, user: str, temperature: float, max_tokens: int
) -> str:
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=600,
                    extra_body=_NO_THINK,
                )
                return resp.choices[0].message.content or ""
            except Exception:  # noqa: BLE001
                if attempt >= 2:
                    raise
                try:
                    async with httpx.AsyncClient(timeout=60.0) as h:
                        _ = await h.get(f"{LLM_ROUTER}/router/restart")
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(3.0)
    return ""


def chat(
    model: str, system: str, user: str, temperature: float = 0.0, max_tokens: int = 2000
) -> str:
    """
    One blocking chat completion (thinking off)
    """
    return asyncio.run(_chat_async(model, system, user, temperature, max_tokens))


def parse_json(text: str) -> Any:
    """
    Strip fences / prose and parse the first JSON object or array
    """
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        m = re.search(r"(\{.*\}|\[.*\])", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:  # noqa: BLE001
                return None
    return None
