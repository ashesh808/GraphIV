"""
Fetches what Semantic Scholar and OpenAlex call each held-out paper, for the survey comparison

Both are cached in assets/data/survey_sources.json with the date they were fetched, as both change
A paper a service does not resolve stays null, and a throttle is waited out, never read as an answer
"""

from __future__ import annotations

import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from style import DATA

CACHE = DATA / "survey_sources.json"
SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=publicationTypes"
OPENALEX = "https://api.openalex.org/works"
# the batch endpoint takes up to 500 ids, and OpenAlex's filter up to 100 values
SCHOLAR_BATCH, OPENALEX_BATCH = 500, 50


def call(request: urllib.request.Request, tries: int = 8) -> Any:
    """
    One request, waiting out a throttle or a server error with a doubling pause

    Args:
        request: The request.
        tries: How many times to send it.

    Returns:
        The parsed json body.

    Raises:
        urllib.error.HTTPError: On a refusal that waiting does not fix.
        RuntimeError: When every try was throttled.
    """
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            print(f"[types] {error.code}, waiting {5 * 2**attempt}s", flush=True)
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"{request.full_url} was refused {tries} times")


def semantic_scholar(ids: list[str]) -> dict[str, list[str] | None]:
    """
    Each paper's publication types, empty when Semantic Scholar has none for it

    Args:
        ids: arXiv ids.

    Returns:
        The types per id, None for a paper it does not resolve.
    """
    out: dict[str, list[str] | None] = {}
    for start in range(0, len(ids), SCHOLAR_BATCH):
        chunk = ids[start : start + SCHOLAR_BATCH]
        body = json.dumps({"ids": [f"ARXIV:{i}" for i in chunk]}).encode()
        request = urllib.request.Request(
            SCHOLAR, data=body, headers={"Content-Type": "application/json"}
        )
        for arxiv_id, paper in zip(chunk, call(request), strict=True):
            out[arxiv_id] = None if paper is None else list(paper.get("publicationTypes") or [])
        print(f"[types] Semantic Scholar {len(out):,}/{len(ids):,}", flush=True)
        time.sleep(3)
    return out


def openalex(ids: list[str]) -> dict[str, str | None]:
    """
    Each paper's work type, looked up by the DOI arXiv mints for it

    Args:
        ids: arXiv ids.

    Returns:
        The type per id, None for a paper it does not resolve.
    """
    out: dict[str, str | None] = dict.fromkeys(ids)
    for start in range(0, len(ids), OPENALEX_BATCH):
        chunk = {i.lower(): i for i in ids[start : start + OPENALEX_BATCH]}
        dois = "|".join(f"10.48550/arxiv.{i}" for i in chunk)
        query = urllib.parse.urlencode(
            {"filter": f"doi:{dois}", "select": "doi,type,locations", "per-page": 100}
        )
        for work in call(urllib.request.Request(f"{OPENALEX}?{query}"))["results"]:
            # a paper with a published version comes back under the journal's DOI, with arXiv's
            # DOI only among its locations
            names = [str(work.get("doi"))] + [str(at.get("id")) for at in work["locations"]]
            for name in names:
                key = name.lower().rpartition("10.48550/arxiv.")[2]
                if key in chunk:
                    out[chunk[key]] = work.get("type")
        time.sleep(0.3)
    print(f"[types] OpenAlex {sum(t is not None for t in out.values()):,}/{len(ids):,}", flush=True)
    return out


def load(ids: list[str]) -> dict[str, Any]:
    """
    Both services' types for the papers, fetched once and then read from the cache

    Args:
        ids: arXiv ids.

    Returns:
        The fetch date, and each service's types by id.
    """
    if CACHE.is_file():
        cached: dict[str, Any] = json.loads(CACHE.read_text(encoding="utf-8"))
        if set(ids) <= set(cached["semantic_scholar"]) and set(ids) <= set(cached["openalex"]):
            return cached
    data = {
        "fetched": datetime.date.today().isoformat(),
        "semantic_scholar": semantic_scholar(ids),
        "openalex": openalex(ids),
    }
    _ = CACHE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data
