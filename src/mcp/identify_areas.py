"""
One question, or one list of papers, into the areas someone would have to read separately

A question spanning four fields embeds into a region that is none of them, so the split comes first
A list of papers is split by what the papers are about, and each area is kept under an id
"""

from __future__ import annotations

import hashlib
import json
import logging
from itertools import combinations
from typing import Any

import psycopg

from src.core import llm
from src.mcp.state import Area, Handles, keep_area
from src.miner.store import mean_vector, read_vectors
from src.retrieve import people as persons

LOG = logging.getLogger(__name__)

PROMPT = """A researcher asked this.

{question}

Split it into the distinct research areas someone would have to read separately to answer it.

Return json only, no preamble:
{{"areas": [{{"area": "...", "methods": ["...", "..."], "question": "...", "why": "..."}}]}}

Rules:
- Between 2 and {cap} areas, and fewer is better than more.
- "area" names a field as a paper title would phrase it, 4 to 12 words.
- "methods" lists 4 to 8 technical terms a paper in that area would use in its abstract.
- Two areas whose "methods" would be the same are one area, so merge them.
- "question" is what this area alone has to answer, 10 to 25 words.
- "why" says in one sentence what the researcher needs from this area.
- Name no specific papers and no authors.
"""


PAPERS_PROMPT = """Below is a list of research papers. Group them into areas by what they are about:
one area when they share one topic, more only when they clearly split into separate topics. Every
paper belongs to exactly one area. Name each area as a paper title would phrase it, 4 to 12 words,
and say in one sentence what its papers share.{scope}

Return json only, no preamble:
{{"areas": [{{"area": "...", "why": "...", "papers": [1, 2]}}]}}

{body}
"""

SCOPE = """

The researcher only cares about: {scope}. Put every paper outside that into one area named
"{outside}", and group the rest as above."""

NAMES_PROMPT = """Below are groups of research papers, each under the topic a tree placed it in.
Name each group as a paper title would phrase it, 4 to 12 words, from what its papers are about
rather than from the topic's own name, and say in one sentence what its papers share.

Return json only, no preamble:
{{"areas": [{{"group": 1, "area": "...", "why": "..."}}]}}

{body}
"""

UNPLACED_NAME = "papers the topic tree has not placed yet"
# the titles each group shows the model, which is enough to name it
TITLES_PER_GROUP = 12

OUTSIDE = "outside scope"
# the most papers one split reads
MAX_PAPERS = 200
# past this many papers the split reads titles alone, so a whole author's list fits one call
TITLES_ONLY = 60
ABSTRACT_CHARS = 500
LISTED = 25
# areas closer than this are one area, measured on ten-paper lists drawn from two reviews
MERGE_FLOOR = 0.60
# one author's papers all clear that floor, so only a short list is merged
MERGE_UP_TO = 30
ID_CHARS = 10

DETAILS = "SELECT arxiv_id, title, abstract, date FROM papers WHERE arxiv_id = ANY(%s)"


def anchor(area: str, methods: list[str]) -> str:
    """
    The manufactured document an area is measured against

    The corpus is full of abstracts and a question does not read like one, so the words a paper in
    the area would use are glued into a line that does.

    Args:
        area: The name of the field.
        methods: The method words.

    Returns:
        The line.
    """
    return f"{area}. {', '.join(methods)}" if methods else area


def merge(areas: list[dict[str, Any]], vectors: dict[str, list[float]]) -> list[dict[str, Any]]:
    """
    Joins the two closest areas while their mean vectors sit at or above the merge floor

    The area holding what is outside the scope never joins another.

    Args:
        areas: Each area's name, reason and paper ids.
        vectors: Every paper's vector.

    Returns:
        The areas after merging.
    """
    areas = [dict(a) for a in areas]
    while True:
        inside = [i for i, a in enumerate(areas) if a["area"] != OUTSIDE]
        if len(inside) < 2:
            return areas
        means = {
            i: mean_vector([vectors[p] for p in areas[i]["arxiv_ids"] if p in vectors])
            for i in inside
        }
        closest = max(
            (sum(x * y for x, y in zip(means[i], means[j], strict=False)), i, j)
            for i, j in combinations(inside, 2)
        )
        if closest[0] < MERGE_FLOOR:
            return areas
        _, i, j = closest
        areas[i]["arxiv_ids"] += areas[j]["arxiv_ids"]
        areas[i]["area"] = f"{areas[i]['area']} / {areas[j]['area']}"
        del areas[j]


def split_papers(handles: Handles, arxiv_ids: list[str], scope: str) -> dict[str, Any]:
    """
    One list of papers into areas, each kept under an id so later calls never repeat the list

    Args:
        handles: The shared handles.
        arxiv_ids: The papers, in the order they were given.
        scope: What the researcher cares about, empty when everything counts.

    Returns:
        The areas with their papers, and how many papers fell outside the scope.
    """
    ids = list(dict.fromkeys(arxiv_ids))[:MAX_PAPERS]
    with psycopg.connect(handles.dsn) as conn:
        meta = {
            str(a): (" ".join(str(t or "").split()), " ".join(str(ab or "").split()), str(d))
            for a, t, ab, d in conn.execute(DETAILS, (ids,)).fetchall()
        }
    ids = [a for a in ids if a in meta]
    if not ids:
        return {"error": "none of these papers is in the corpus"}
    if len(ids) > TITLES_ONLY:
        body = "\n".join(f"[{i + 1}] {meta[a][0]}" for i, a in enumerate(ids))
    else:
        body = "\n\n".join(
            f"[{i + 1}] {meta[a][0]}\n{meta[a][1][:ABSTRACT_CHARS]}" for i, a in enumerate(ids)
        )
    told = SCOPE.format(scope=scope, outside=OUTSIDE) if scope else ""
    reply = handles.model.ask(PAPERS_PROMPT.format(body=body, scope=told), max_tokens=4000)
    parsed = llm.parse_json(reply)
    raw = parsed.get("areas") if isinstance(parsed, dict) else None
    areas: list[dict[str, Any]] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        members = [
            ids[n - 1] for n in entry.get("papers", []) if isinstance(n, int) and 1 <= n <= len(ids)
        ]
        name = " ".join(str(entry.get("area", "")).split())
        if members and name:
            outside = name.lower() == OUTSIDE
            areas.append(
                {
                    "area": OUTSIDE if outside else name,
                    "why": " ".join(str(entry.get("why", "")).split()),
                    "arxiv_ids": list(dict.fromkeys(members)),
                }
            )
    if not areas:
        areas = [{"area": scope or "the papers given", "why": "", "arxiv_ids": ids}]
    if len(ids) <= MERGE_UP_TO:
        areas = merge(areas, read_vectors(handles.dsn, ids))
    out: list[dict[str, Any]] = []
    left = 0
    for area in areas:
        if area["area"] == OUTSIDE:
            left += len(area["arxiv_ids"])
            continue
        key = hashlib.sha1(
            "|".join([area["area"], *sorted(area["arxiv_ids"])]).encode()
        ).hexdigest()
        held = keep_area(Area(key[:ID_CHARS], area["area"], area["why"], area["arxiv_ids"]))
        out.append(
            {
                "area_id": held.area_id,
                "area": held.area,
                "why": held.why,
                "count": len(held.arxiv_ids),
                "papers": [
                    {"arxiv_id": a, "title": meta[a][0], "date": meta[a][2]}
                    for a in held.arxiv_ids[:LISTED]
                ],
            }
        )
    placed = {a for area in areas for a in area["arxiv_ids"]}
    LOG.info("split %d papers into %d areas, %d outside the scope", len(ids), len(out), left)
    return {
        "papers": len(ids),
        "areas": out,
        "outside_scope": left,
        "unplaced": len([a for a in ids if a not in placed]),
    }


def found_people(handles: Handles, people: list[dict[str, Any]]) -> tuple[list[str], list[Any]]:
    """
    The union of what each named person wrote, and what each name matched

    Args:
        handles: The shared handles.
        people: Each as {"name": ..., "known": [...]}.

    Returns:
        The papers, each once, and one entry per person with their counts.

    Raises:
        ValueError: When a person has no name or no known paper.
    """
    found = [persons.find(handles.dsn, p) for p in persons.as_people(people)]
    union = list(dict.fromkeys(a for f in found for a in f.kept))
    told = [
        {
            "name": f.person.name,
            "known": list(f.person.known),
            "matched": f.candidates,
            "kept": len(f.kept),
        }
        for f in found
    ]
    return union, told


def split_people(handles: Handles, people: list[dict[str, Any]]) -> dict[str, Any]:
    """
    People's papers into one area per parent topic, each named from its own titles

    Args:
        handles: The shared handles.
        people: Each as {"name": ..., "known": [...]}.

    Returns:
        The areas with their papers, and what each person's name matched.
    """
    try:
        union, told = found_people(handles, people)
    except ValueError as error:
        return {"error": str(error)}
    if not union:
        return {"error": "none of the known papers lists its person as an author", "people": told}
    with psycopg.connect(handles.dsn) as conn:
        meta = {
            str(a): (" ".join(str(t or "").split()), str(d))
            for a, t, _, d in conn.execute(DETAILS, (union,)).fetchall()
        }
    groups = sorted(persons.topics(handles.dsn, union).items(), key=lambda kv: -len(kv[1]))
    tree = persons.topic_names(handles.dsn)
    body = "\n\n".join(
        f"Group {i + 1}, topic: {tree.get(key, UNPLACED_NAME)}\n"
        + "\n".join(f"- {meta[a][0]}" for a in ids[:TITLES_PER_GROUP] if a in meta)
        for i, (key, ids) in enumerate(groups)
    )
    reply = handles.model.ask(NAMES_PROMPT.format(body=body), max_tokens=4000)
    parsed = llm.parse_json(reply)
    named: dict[int, dict[str, Any]] = {}
    listed = parsed.get("areas") if isinstance(parsed, dict) else None
    for entry in listed if isinstance(listed, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("group"), int):
            named[entry["group"]] = entry
    out: list[dict[str, Any]] = []
    for i, (key, ids) in enumerate(groups):
        entry = named.get(i + 1, {})
        name = " ".join(str(entry.get("area", "")).split()) or tree.get(key, UNPLACED_NAME)
        area_key = hashlib.sha1("|".join(["people", name, *sorted(ids)]).encode()).hexdigest()
        held = keep_area(
            Area(
                area_key[:ID_CHARS],
                name,
                " ".join(str(entry.get("why", "")).split()),
                ids,
                pinned=True,
            )
        )
        out.append(
            {
                "area_id": held.area_id,
                "area": held.area,
                "topic": tree.get(key, UNPLACED_NAME),
                "why": held.why,
                "count": len(ids),
                "papers": [
                    {"arxiv_id": a, "title": meta[a][0], "date": meta[a][1]}
                    for a in ids[:LISTED]
                    if a in meta
                ],
            }
        )
    LOG.info("split %d papers of %d people into %d topics", len(union), len(told), len(out))
    return {"people": told, "papers": len(union), "areas": out}


def identify_areas(
    handles: Handles,
    question: str = "",
    cap: int = 4,
    people: list[dict[str, Any]] | None = None,
    arxiv_ids: list[str] | None = None,
    scope: str = "",
) -> str:
    """
    The areas one question breaks into, the areas people work in, or the areas a paper list covers

    Args:
        handles: The shared handles.
        question: What was asked, when the split starts from a question.
        cap: The most areas a question breaks into.
        people: Authors whose papers are split by topic, each {"name": ..., "known": [...]}.
        arxiv_ids: Papers to split instead.
        scope: What the researcher cares about, which a paper list is held to.

    Returns:
        The areas as json.
    """
    if people:
        return json.dumps(split_people(handles, people), indent=2)
    if arxiv_ids:
        return json.dumps(split_papers(handles, list(arxiv_ids), scope), indent=2)
    if not question:
        return json.dumps({"error": "pass a question, people, or arxiv_ids to split"})
    reply = handles.model.ask(PROMPT.format(question=question, cap=cap), max_tokens=900)
    parsed = llm.parse_json(reply)
    raw = parsed.get("areas") if isinstance(parsed, dict) else None
    out: list[dict[str, object]] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        name = " ".join(str(entry.get("area", "")).split())
        methods = [" ".join(str(m).split()) for m in entry.get("methods", []) if str(m).strip()]
        asked = " ".join(str(entry.get("question", "")).split())
        if not name or not asked:
            continue
        out.append(
            {
                "area": name,
                "methods": methods[:8],
                "question": asked,
                "anchor": anchor(name, methods[:8]),
                "why": " ".join(str(entry.get("why", "")).split()),
            }
        )
    if not out:
        out = [{"area": "", "methods": [], "question": question, "anchor": "", "why": ""}]
    LOG.info("split into %d areas", len(out))
    return json.dumps({"areas": out[:cap]}, indent=2)
