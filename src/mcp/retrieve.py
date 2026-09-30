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

from src.core.schema import Grade, Paper, Query
from src.mcp.effort import Effort, level
from src.mcp.state import Handles, Held, keep, make_id, overlap
from src.miner import era, rank, reader
from src.miner.recipe import read_recipe as read_miner
from src.miner.store import read_cosines, read_seed
from src.retrieve.cosine import CosineRetriever
from src.retrieve.recipe import build_pipeline, get_seed_limit, read_recipe

LOG = logging.getLogger(__name__)

CENTRAL = ("core", "frontier", "foundational")
FLOOR = 5
# the modes that always start from a paper, the closest one to the question when none is named
SEEDED = ("ancestry", "evolution")
NEAREST = 100


def find_seed(
    handles: Handles, question: str, arxiv_id: str, mode: str, floor: date | None, cap: date
) -> tuple[Paper, list[float]] | None:
    """
    The paper a search starts from, which is the one named or the closest one inside the window

    Args:
        handles: The shared handles.
        question: What was asked, which picks the paper when none is named.
        arxiv_id: The paper named, empty when none was.
        mode: Which recipe, since only some modes pick a paper on their own.
        floor: The earliest date the paper may carry.
        cap: The latest date the paper may carry.

    Returns:
        The paper and its stored vector, or None when the search starts from the question.
    """
    if not arxiv_id and mode in SEEDED and question:
        query = Query(text=question, emb=handles.embed(question), max_date=cap)
        near = CosineRetriever(handles.dsn).retrieve(query, NEAREST)
        arxiv_id = next((p.arxiv_id for p in near if floor is None or p.date >= floor), "")
    return read_seed(handles.dsn, arxiv_id) if arxiv_id else None


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
    question: str = "",
    arxiv_id: str = "",
    methods: list[str] | None = None,
    mode: str = "survey",
    date_min: str = "",
    date_max: str = "",
    seen: list[str] | None = None,
    effort: str = "standard",
) -> str:
    """
    Everything the mechanical path and the reader know about one area

    Args:
        handles: The shared handles.
        question: The area's own question, or the whole question when it was not split.
        arxiv_id: The paper to start from, whose own vector replaces the question's.
        methods: The area's method words, which build what the gate measures against.
        mode: survey, frontier, consensus, ancestry or evolution, which picks the recipe.
        date_min: The earliest date a returned paper may carry, iso, no floor when empty.
        date_max: The date the corpus is capped at, iso, today when empty.
        seen: Ids of rankings made earlier, against which the overlap is reported.
        effort: quick, standard or deep.

    Returns:
        The kept papers, the grade histogram and the id the ranking is kept under, as json.
    """
    clock = time.perf_counter()
    spent: dict[str, float] = {}
    hard: Effort = level(effort)
    floor = date.fromisoformat(date_min) if date_min else None
    cap = date.fromisoformat(date_max) if date_max else date.today()
    if not question and not arxiv_id:
        return json.dumps({"error": "pass a question, an arxiv_id or both"})
    seed = find_seed(handles, question, arxiv_id.strip(), mode, floor, cap)
    if arxiv_id and seed is None:
        return json.dumps({"error": f"{arxiv_id} has no vector in this corpus"})
    if seed is not None and not question:
        question = " ".join(seed[0].title.split())
    path = handles.recipe(mode)
    recipe = read_recipe(path)
    mining = read_miner(path)

    anchor = f"{question}. {', '.join(methods)}" if methods else question
    vector = seed[1] if seed is not None else handles.embed(question)
    pipeline = build_pipeline(recipe, handles.graph, handles.dsn)
    pool = pipeline.build_pool(question, vector, get_seed_limit(recipe), cap)
    ranked = pipeline.score_pool(question, vector, pool, cap)
    if floor is not None:
        ranked = [p for p in ranked if p.date >= floor]
    spent["retrieve"] = time.perf_counter() - clock

    clock = time.perf_counter()
    if methods:
        cosines = read_cosines(handles.dsn, handles.embed(anchor), [p.arxiv_id for p in ranked])
        ranked = rank.gate(ranked, cosines, mining.gate)
    current = era.detect([p.date for p in ranked], cap)
    recent = [p for p in ranked if current.holds(p.date)]
    # by score alone every slot goes to the oldest cohort, which had the years to collect citations
    reading = era.cohorts(recent, hard.read)
    sid = seed[0].arxiv_id if seed is not None else ""
    pinned = next((p for p in ranked if p.arxiv_id == sid), seed[0] if seed is not None else None)
    if pinned is not None and all(p.arxiv_id != sid for p in reading):
        reading.append(pinned)
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
    # the seed is what the search is about, so it leads whatever the blend thought of it
    if pinned is not None:
        pinned = next((p for p in kept if p.arxiv_id == sid), pinned)
        kept = [pinned] + [p for p in kept if p.arxiv_id != sid][: hard.keep - 1]
    spent["read"] = time.perf_counter() - clock

    held = keep(
        Held(
            query_id=make_id(anchor, mode, date_min, cap.isoformat(), sid),
            question=question,
            anchor=anchor,
            mode=mode,
            asked=cap,
            seed=sid,
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
        "seed": sid,
        "date_min": date_min,
        "date_max": cap.isoformat(),
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
