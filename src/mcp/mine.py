"""
A list of papers into what the field argues with, how it got there and what has answered it since

The list arrives as the id of an earlier retrieval, since the papers are already held here
Everything is read off the intent-labeled citation graph, so nothing in the result is invented
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from src.core.schema import Paper
from src.mcp.effort import level
from src.mcp.state import Handles, get, get_area
from src.miner.miner import Miner
from src.miner.recipe import read_recipe
from src.miner.store import mean_vector, read_papers, read_vectors

LOG = logging.getLogger(__name__)

TITLE_CHARS = 90
SENTENCE_CHARS = 300


def clean(title: str) -> str:
    """
    One title on one line

    Args:
        title: The raw title.

    Returns:
        The cleaned title.
    """
    return " ".join(title.split())[:TITLE_CHARS]


def mine(
    handles: Handles,
    query_id: str = "",
    arxiv_ids: list[str] | None = None,
    question: str = "",
    mode: str = "survey",
    effort: str = "standard",
    area_id: str = "",
) -> str:
    """
    What a set of papers means together, read off the citations between and around them

    Args:
        handles: The shared handles.
        query_id: What a retrieve call returned, whose kept papers are mined.
        arxiv_ids: Papers to mine instead, when the caller picked them itself.
        question: What to hold the result to, when papers were named rather than retrieved.
        mode: survey, frontier, consensus, ancestry or evolution, which picks the recipe.
        effort: quick, standard or deep.
        area_id: An area identify_areas split a paper list into, whose own papers are mined.

    Returns:
        The magnets, the lineages, the disputes, the successors and the connectors, as json.
    """
    clock = time.perf_counter()
    hard = level(effort)
    held = get(query_id) if query_id else None
    if query_id and held is None:
        return json.dumps({"error": f"no ranking under {query_id}, this server never made it"})
    area = get_area(area_id) if area_id else None
    if area_id and area is None:
        return json.dumps({"error": f"no area under {area_id}, this server never made it"})
    if held is not None:
        papers: list[Paper] = held.kept
        vector, asked, mode = held.vector, held.asked, held.mode
        question = question or held.question
    elif area is not None:
        question = question or area.area
        vector = mean_vector(list(read_vectors(handles.dsn, area.arxiv_ids).values()))
        asked = date.today()
        papers = read_papers(handles.dsn, vector, area.arxiv_ids)
        if not papers:
            return json.dumps({"error": "none of that area's papers is in the corpus"})
    else:
        if not arxiv_ids:
            return json.dumps(
                {
                    "error": "pass a query_id from retrieve, an area_id from identify_areas,"
                    " or arxiv_ids"
                }
            )
        if not question:
            return json.dumps({"error": "naming papers rather than a query_id needs a question"})
        vector = handles.embed(question)
        asked = date.today()
        papers = read_papers(handles.dsn, vector, arxiv_ids)
        if not papers:
            return json.dumps({"error": "none of those ids is in the corpus"})

    pinned = (held is not None and held.pinned) or (area is not None and area.pinned)
    found = Miner(handles.dsn, handles.graph, read_recipe(handles.recipe(mode))).mine(
        papers, vector, asked, expand=not pinned
    )
    names = found.papers
    out: dict[str, Any] = {
        "query_id": query_id,
        "area_id": area_id,
        "counts": found.counts | {"seconds": round(time.perf_counter() - clock, 1)},
        "magnets": [
            {
                "arxiv_id": m.node,
                "title": clean(names[m.node].title) if m.node in names else "",
                "weight": round(m.weight, 3),
                "argued": m.argued,
            }
            for m in found.magnets[: hard.magnets]
        ],
        "lineages": [
            {
                "runs": line.runs,
                "papers": [
                    {
                        "arxiv_id": n,
                        "date": names[n].date.isoformat(),
                        "title": clean(names[n].title),
                        "magnet": n in line.magnets,
                    }
                    for n in line.nodes
                    if n in names
                ],
            }
            for line in found.lineages[: hard.lineages]
        ],
        "disputes": [
            {
                "arxiv_id": e.target,
                "title": clean(names[e.target].title) if e.target in names else "",
                "intent": e.intent,
                "sentence": e.sentence[:SENTENCE_CHARS],
            }
            for e in found.disputes[: hard.disputes]
        ],
        "successors": [
            {
                "arxiv_id": s.paper.arxiv_id,
                "date": s.paper.date.isoformat(),
                "title": clean(s.paper.title),
                "reach": s.reach,
                "intents": sorted(set(s.targets.values())),
                "sentence": s.sentences[0][:SENTENCE_CHARS] if s.sentences else "",
            }
            for s in found.successors[: hard.successors]
        ],
        "connectors": [
            {"arxiv_id": n, "title": clean(names[n].title)}
            for n in found.connectors[: hard.magnets]
            if n in names
        ],
    }
    LOG.info("mined %s: %s", query_id or area_id or "a named list", found.counts)
    return json.dumps(out, indent=2)
