"""
The local router, with every completion cached by the hash of the prompt that produced it

A cached run replays with no GPU, which is what makes an ablation over these stages affordable
Prompts go out in parallel because the router serves a batched model
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

LOG = logging.getLogger(__name__)

PARALLEL = 8
ATTEMPTS = 3


class Gemma:
    """
    An OpenAI-compatible endpoint that remembers what it said
    """

    def __init__(
        self,
        api: str,
        model: str,
        cache: str | Path,
        *,
        api_key: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 600,
        reasoning_effort: str | None = "none",
        raise_on_error: bool = False,
    ) -> None:
        """
        Holds the endpoint and the directory a completion is written into

        Args:
            api: The OpenAI-compatible base url.
            model: Which model to ask.
            cache: Directory the completions are written into.
            api_key: Optional bearer credential for the external endpoint.
            headers: Additional headers required by the configured provider.
            timeout: Timeout in seconds for one request.
            reasoning_effort: Legacy router option; None omits it for standard providers.
            raise_on_error: Surface service failures instead of returning an empty answer.
        """
        self.api = api.rstrip("/")
        self.model = model
        self.cache = Path(cache)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("LLM request timeout must be positive")
        endpoint = urlsplit(self.api)
        if endpoint.username or endpoint.password:
            raise ValueError("LLM credentials must be supplied as request headers")
        if (
            (api_key or headers)
            and endpoint.scheme != "https"
            and not (
                endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("Authenticated LLM services require HTTPS outside localhost")
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.raise_on_error = raise_on_error
        self.headers = {"Content-Type": "application/json", **dict(headers or {})}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
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

    def post(self, prompt: str, max_tokens: int) -> tuple[str, bool]:
        """
        One completion against the router, retried, with reasoning off

        Args:
            prompt: The user message.
            max_tokens: The completion budget.

        Returns:
            The reply, empty when every attempt failed, and whether the budget cut it off.
        """
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        request = urllib.request.Request(
            f"{self.api}/chat/completions",
            data=json.dumps(body).encode(),
            headers=self.headers,
        )
        failure = "LLM service returned no answer"
        for _ in range(ATTEMPTS):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                choice = payload["choices"][0]
                reply = str(choice["message"]["content"] or "")
            except urllib.error.HTTPError as error:
                failure = f"LLM service returned HTTP {error.code}"
                if error.code in (400, 401, 403, 404):
                    break
                continue
            except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError, IndexError):
                failure = "LLM service could not return a valid completion"
                continue
            if reply.strip():
                return reply, choice.get("finish_reason") == "length"
        LOG.warning("the router returned nothing after %d attempts", ATTEMPTS)
        if self.raise_on_error:
            raise RuntimeError(failure)
        return "", False

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
        reply, cut = self.post(prompt, max_tokens)
        # a reply cut at the budget parses as nothing, so caching it would replay the failure
        if reply.strip() and not cut:
            _ = path.write_text(reply, encoding="utf-8")
        elif cut:
            LOG.warning("a reply ran out of its %d token budget and was not cached", max_tokens)
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
