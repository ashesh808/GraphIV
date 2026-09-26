"""
One area into the papers worth reading, which is the retriever, the gate and the reader in one call

The ranking stays here and the caller is given the id it is kept under, since it is thousands long
Everything tuned sits in the recipe the mode names, so no number the caller sends changes the score
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from src.core.schema import Grade, Paper
from src.mcp.effort import Effort, level
from src.mcp.state import Handles, Held, keep, make_id, overlap
from src.miner import era, rank, reader
from src.miner.recipe import read_recipe as read_miner
from src.miner.store import read_cosines
from src.retrieve.recipe import build_pipeline, get_seed_limit, read_recipe

LOG = logging.getLogger(__name__)

CENTRAL = ("core", "frontier", "foundational")
FLOOR = 5


def pick(papers: list[Paper], grades: dict[str, Grade], limit: int) -> list[Paper]:
    """
    The papers that came back central, or the merely relevant ones when too few did

    Args:
        papers: The graded ranking, best first.
        grades: What the reader said.
        limit: The most to keep.

    Returns:
        The kept papers.
    """
    blank = Grade(role="", relevance=0)
    central = [p for p in papers if grades.get(p.arxiv_id, blank).role in CENTRAL]
    if len(central) >= FLOOR:
        return central[:limit]
    relevant = [p for p in papers if grades.get(p.arxiv_id, blank).relevance >= 1]
    return (central or relevant or papers)[:limit]


def retrieve(
    handles: Handles,
    question: str,
    methods: list[str] | None = None,
    mode: str = "survey",
    asked: str = "",
    seen: list[str] | None = None,
    effort: str = "standard",
) -> str:
    """
    Everything the mechanical path and the reader know about one area

    Args:
        handles: The shared handles.
        question: The area's own question, or the whole question when it was not split.
        methods: The area's method words, which build what the gate measures against.
        mode: survey, frontier or consensus, which picks the recipe.
        asked: The date the corpus is capped at, iso, today when empty.
        seen: Ids of rankings made earlier, against which the overlap is reported.
        effort: quick, standard or deep.

    Returns:
        The kept papers, the grade histogram and the id the ranking is kept under, as json.
    """
    clock = time.perf_counter()
    spent: dict[str, float] = {}
    hard: Effort = level(effort)
    cap = date.fromisoformat(asked) if asked else date.today()
    path = handles.recipe(mode)
    recipe = read_recipe(path)
    mining = read_miner(path)

    anchor = f"{question}. {', '.join(methods)}" if methods else question
    vector = handles.embed(question)
    pipeline = build_pipeline(recipe, handles.graph, handles.dsn)
    pool = pipeline.build_pool(question, vector, get_seed_limit(recipe), cap)
    ranked = pipeline.score_pool(question, vector, pool, cap)
    spent["retrieve"] = time.perf_counter() - clock

    clock = time.perf_counter()
    if methods:
        cosines = read_cosines(handles.dsn, handles.embed(anchor), [p.arxiv_id for p in ranked])
        ranked = rank.gate(ranked, cosines, mining.gate)
    current = era.detect([p.date for p in ranked], cap)
    recent = [p for p in ranked if current.holds(p.date)]
    # by score alone every slot goes to the oldest cohort, which had the years to collect citations
    reading = era.cohorts(recent, hard.read)
    spent["gate"] = time.perf_counter() - clock

    clock = time.perf_counter()
    grades = reader.grade(handles.model, question, reading)
    graded = reader.keep(reading, grades)
    kept = rank.blend(
        pick(graded, grades, hard.keep),
        grades,
        handles.graph,
        cap,
        mining.graph_weight,
        mining.relevance_weight,
    )
    spent["read"] = time.perf_counter() - clock

    held = keep(
        Held(
            query_id=make_id(anchor, mode, cap.isoformat()),
            question=question,
            anchor=anchor,
            mode=mode,
            asked=cap,
            vector=vector,
            ranked=ranked,
            kept=kept,
            grades=grades,
            era=current.year,
            pool=len(pool),
            seconds=sum(spent.values()),
        )
    )
    share, per = overlap(held.head, seen or [])
    counts: dict[str, int] = {}
    for one in grades.values():
        counts[one.role] = counts.get(one.role, 0) + 1

    out: dict[str, Any] = {
        "query_id": held.query_id,
        "mode": mode,
        "anchor": anchor,
        "era_starts": current.year,
        "counts": {
            "pool": len(pool),
            "current": len(recent),
            "read": len(reading),
            "kept": len(kept),
            "seconds": round(sum(spent.values()), 1),
        },
        "grades": counts,
        "new_share": round(share, 3),
        "overlap": {k: round(v, 3) for k, v in per.items()},
        "papers": [
            {
                "arxiv_id": p.arxiv_id,
                "date": p.date.isoformat(),
                "title": " ".join(p.title.split()),
                "role": grades[p.arxiv_id].role if p.arxiv_id in grades else "",
                "relevance": grades[p.arxiv_id].relevance if p.arxiv_id in grades else 0,
            }
            for p in kept
        ],
    }
    LOG.info(
        "%s: pool %d, current %d, kept %d, era %d, new share %.2f",
        held.query_id,
        len(pool),
        len(recent),
        len(kept),
        current.year,
        share,
    )
    return json.dumps(out, indent=2)
