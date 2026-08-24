"""
The chat client every LLM role shares, in async and sync form

Thinking is a per-call mode rather than a per-model choice, so one endpoint serves every role
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from graphiv.core.router import dated, model_status, restart_router
from graphiv.core.settings import LLM_BASE_URL

__all__ = [
    "THINK",
    "NO_THINK",
    "dated",
    "chat",
    "chat_sync",
    "ensure_loaded",
    "parse_json",
]

# server-side chat-template knobs for the thinking channel (llama.cpp / jinja)
THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": True}}
NO_THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": False}}


def _user_content(user: str, images: list[bytes] | None) -> Any:
    """
    Plain string when text-only; OpenAI vision content-array when images are given
    """
    if not images:
        return user
    parts: list[dict[str, Any]] = [{"type": "text", "text": user}]
    for png in images:
        b64 = base64.b64encode(png).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    return parts


async def chat(
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    extra_body: dict[str, object] | None = None,
    images: list[bytes] | None = None,
) -> tuple[str, int, int]:
    """
    One chat completion; returns (text, prompt_tokens, completion_tokens)

        `extra_body` passes server-side knobs (e.g. {"chat_template_kwargs":
        {"enable_thinking": False}} to suppress a thinking model's reasoning channel).
        `images` (PNG bytes) switch the user turn to the OpenAI vision content-array form for
        a multimodal endpoint; omitted -> a plain text message (backward compatible).
    """
    if await model_status(model) is None:
        await restart_router(model)
    msgs: list[ChatCompletionMessageParam] = cast(
        list[ChatCompletionMessageParam],
        ([{"role": "system", "content": dated(system)}] if system else [])
        + [{"role": "user", "content": _user_content(user, images)}],
    )
    # closing the client before asyncio.run tears the loop down avoids a GC-time error
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=1200,
                    extra_body=extra_body or {},
                )
                text = resp.choices[0].message.content or ""
                usage = resp.usage
                pt = int(usage.prompt_tokens) if usage else len(user) // 4
                ct = int(usage.completion_tokens) if usage else len(text) // 4
                return text, pt, ct
            except Exception as e:  # noqa: BLE001
                msg = f"{type(e).__name__}: {str(e)[:120]}"
                if attempt >= 2:
                    print(f"  [chat:{model}] final error: {msg}", flush=True)
                    raise
                print(f"  [chat:{model}] error (attempt {attempt + 1}): {msg}", flush=True)
                await restart_router(model)
    return "", 0, 0


def chat_sync(
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    extra_body: dict[str, object] | None = None,
) -> tuple[str, int, int]:
    """
    Blocking wrapper around chat, for callers with no event loop
    """
    return asyncio.run(chat(model, system, user, temperature, max_tokens, extra_body=extra_body))


async def ensure_loaded(model: str) -> None:
    """
    Warm the model once (so concurrent callers don't each trigger a restart)
    """
    if await model_status(model) is None:
        await restart_router(model)


def parse_json(text: str) -> Any:
    """
    Strip markdown fences / prose and parse the first JSON object/array
    """
    import json
    import re

    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    # a model can return any malformed shape, and a parse failure must not kill the run
    except Exception:  # noqa: BLE001
        m = re.search(r"(\{.*\}|\[.*\])", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            # a model can return any malformed shape, and a parse failure must not kill the run
            except Exception:  # noqa: BLE001
                return None
    return None
