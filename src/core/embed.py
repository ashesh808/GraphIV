"""
The query vector, from the endpoint the documents were encoded with

Documents carry a prompt prefix, so a query missing its own lands elsewhere in the space
"""

from __future__ import annotations

import json
import math
import urllib.request

QUERY_PREFIX = "search_query: "
TIMEOUT = 180


def embed(api: str, model: str, text: str) -> list[float]:
    """
    One query vector, unit normalized

    Args:
        api: The embedding server's base url.
        model: Which model to ask.
        text: The question.

    Returns:
        The vector.
    """
    request = urllib.request.Request(
        f"{api.rstrip('/')}/v1/embeddings",
        data=json.dumps({"model": model, "input": [f"{QUERY_PREFIX}{text}"]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = [float(x) for x in json.load(response)["data"][0]["embedding"]]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]
