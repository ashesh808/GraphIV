"""
The query vector, from the endpoint the documents were encoded with

Documents carry a prompt prefix, so a query missing its own lands elsewhere in the space
"""

from __future__ import annotations

import json
import math
import urllib.request
from collections.abc import Mapping
from urllib.parse import urlsplit

QUERY_PREFIX = "search_query: "
TIMEOUT = 180


def embed(
    api: str,
    model: str,
    text: str,
    *,
    api_key: str | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = TIMEOUT,
) -> list[float]:
    """
    One query vector, unit normalized

    Args:
        api: The embedding server's base url.
        model: Which model to ask.
        text: The question.
        api_key: Optional bearer credential.
        headers: Additional provider-specific request headers.
        timeout: Request timeout in seconds.

    Returns:
        The vector.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Embedding request timeout must be positive")
    base = api.rstrip("/")
    endpoint = urlsplit(base)
    if endpoint.username or endpoint.password:
        raise ValueError("Embedding credentials must be supplied as request headers")
    if (
        (api_key or headers)
        and endpoint.scheme != "https"
        and not (
            endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        )
    ):
        raise ValueError("Authenticated embedding services require HTTPS outside localhost")
    url = (
        base
        if base.endswith("/embeddings")
        else f"{base}/embeddings"
        if base.endswith("/v1")
        else f"{base}/v1/embeddings"
    )
    request_headers = {"Content-Type": "application/json", **dict(headers or {})}
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "input": [f"{QUERY_PREFIX}{text}"]}).encode(),
        headers=request_headers,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = [float(x) for x in json.load(response)["data"][0]["embedding"]]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]
