"""
The local router, with every completion cached by the hash of the prompt that produced it

A cached run replays with no GPU, which is what makes an ablation over these stages affordable
Prompts go out in parallel because the router serves a batched model
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LOG = logging.getLogger(__name__)

PARALLEL = 8
ATTEMPTS = 3


class Gemma:
    """
    An OpenAI-compatible endpoint that remembers what it said
    """

    def __init__(self, api: str, model: str, cache: str | Path) -> None:
        """
        Holds the endpoint and the directory a completion is written into

        Args:
            api: The OpenAI-compatible base url.
            model: Which model to ask.
            cache: Directory the completions are written into.
        """
        self.api = api.rstrip("/")
        self.model = model
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, prompt: str, max_tokens: int) -> Path:
        """
        Where one completion lives

        The budget is part of the key because it changes what comes back.

        Args:
            prompt: The user message.
            max_tokens: The completion budget.

        Returns:
            The cache path.
        """
        stamp = hashlib.sha1(f"{self.model}|{max_tokens}|{prompt}".encode()).hexdigest()[:16]
        return self.cache / f"{stamp}.txt"

    def post(self, prompt: str, max_tokens: int) -> str:
        """
        One completion against the router, retried, with reasoning off

        Args:
            prompt: The user message.
            max_tokens: The completion budget.

        Returns:
            The reply, empty when every attempt failed.
        """
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "reasoning_effort": "none",
        }
        request = urllib.request.Request(
            f"{self.api}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        for _ in range(ATTEMPTS):
            try:
                with urllib.request.urlopen(request, timeout=600) as response:
                    payload = json.load(response)
                reply = str(payload["choices"][0]["message"]["content"] or "")
            except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError):
                continue
            if reply.strip():
                return reply
        LOG.warning("the router returned nothing after %d attempts", ATTEMPTS)
        return ""

    def ask(self, prompt: str, max_tokens: int = 512) -> str:
        """
        One completion, read from the cache when the same prompt has been asked before

        Args:
            prompt: The user message.
            max_tokens: The completion budget.

        Returns:
            The reply.
        """
        path = self.get_cache_path(prompt, max_tokens)
        if path.exists():
            return path.read_text(encoding="utf-8")
        reply = self.post(prompt, max_tokens)
        if reply.strip():
            _ = path.write_text(reply, encoding="utf-8")
        return reply

    def ask_many(self, prompts: list[str], max_tokens: int = 512) -> list[str]:
        """
        Many completions at once, in the order they were asked

        Args:
            prompts: One user message each.
            max_tokens: The completion budget for all of them.

        Returns:
            One reply per prompt.
        """
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            return list(pool.map(lambda p: self.ask(p, max_tokens), prompts))


def parse_json(reply: str) -> dict[str, object] | None:
    """
    The first json object in a reply, whatever the model wrapped it in

    Args:
        reply: The raw completion.

    Returns:
        The parsed object, or None when there is not one.
    """
    fenced = re.sub(r"^```[a-z]*\s*|\s*```$", "", reply.strip(), flags=re.MULTILINE)
    start, end = fenced.find("{"), fenced.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        got = json.loads(fenced[start : end + 1])
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


def parse_lines(reply: str, limit: int, floor: int = 15) -> list[str]:
    """
    A numbered or bulleted list as plain strings

    Args:
        reply: The raw completion.
        limit: The most lines to keep.
        floor: How short a line may be before it is read as a stray marker.

    Returns:
        The lines, stripped of their markers.
    """
    out: list[str] = []
    for line in reply.splitlines():
        got = re.sub(r"^[-*\d.)\s]+", "", line.strip().strip('"')).strip()
        if len(got) >= floor:
            out.append(got)
    return out[:limit]
