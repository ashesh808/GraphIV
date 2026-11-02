"""
The document, assembled from everything the session retrieved and whatever the caller wrote

The caller's prose is carried as written and then checked, so an id it invented never survives
A run is written to disk under its own directory, which is what the dashboard reads
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from typing import Any

from src.core.parse_graph_export import GraphExport
from src.core.schema import Edge, Paper
from src.mcp.effort import Effort, level
from src.mcp.state import Handles, get, get_area, reset
from src.miner.miner import Mined, Miner
from src.miner.recipe import read_recipe
from src.miner.store import read_cosines, read_records
from src.report import ground
from src.report.compose import OPEN_PAPERS, answer, compose, digest, name_lines, unanswered
from src.report.fulltext import FullText, read_open, read_paper
from src.report.render import Area, Draft, LineName, Section, document, inside
from src.report.table import (
    Design,
    Method,
    design,
    extract,
    gaps,
    merge,
    render,
    repair,
    spread,
)

LOG = logging.getLogger(__name__)

SLUG = re.compile(r"[^a-z0-9]+")
SAMPLES = 20
# what the answer is asked from, since the whole review runs past the context a reply needs
EVIDENCE_CHARS = 24000

MISSING_CITATION_TEXT = (
    "Citation sentences are unavailable in this published snapshot. Citation-intent "
    "labels and confidence scores are precomputed model predictions. Citation quotations "
    "and sentence-based dispute analysis are omitted; no citation text was extracted or generated."
)


def _progress(handles: Handles, stage: str) -> None:
    callback = getattr(handles, "progress", None)
    if callback is not None:
        callback(stage)


SENTENCE_CHARS = 300
# a successor sits at least as close to the question as all but the farthest tenth of what was kept
FLOOR_SHARE = 0.1


def slug(text: str, when: date) -> str:
    """
    The directory one run is written to

    Args:
        text: The question.
        when: The date the run was made.

    Returns:
        A name safe on any filesystem.
    """
    stem = SLUG.sub("-", text.lower()).strip("-")[:48] or "run"
    return f"{when.isoformat()}-{stem}"


Session = tuple[list[Paper], list[Area], dict[str, Any], str, str, date, float]


def gather(query_ids: list[str]) -> Session:
    """
    Every paper the session kept, in the order the rankings were made

    Args:
        query_ids: What the retrieve calls returned.

    Returns:
        The papers, the areas, the grades, the question, the mode, the cap and what it all cost.
    """
    papers: dict[str, Paper] = {}
    areas: list[Area] = []
    grades: dict[str, Any] = {}
    question, mode, asked, spent = "", "survey", date.today(), 0.0
    for query_id in query_ids:
        held = get(query_id)
        if held is None:
            continue
        question = question or held.question
        mode, asked, spent = held.mode, held.asked, spent + held.seconds
        grades |= held.grades
        kept = [p.arxiv_id for p in held.kept]
        areas.append(Area(question=held.question, arxiv_ids=kept, seed=held.seed))
        for paper in held.kept:
            papers.setdefault(paper.arxiv_id, paper)
    return list(papers.values()), areas, grades, question, mode, asked, spent


def table(
    handles: Handles, question: str, papers: list[Paper], depth: int
) -> tuple[Design | None, list[Method]]:
    """
    The methods in the papers, side by side on axes this question decides

    Args:
        handles: The shared handles.
        question: What was asked.
        papers: The papers to read, best first.
        depth: How many of them to read in full.

    Returns:
        The design and the merged rows, both empty when no full text landed.
    """
    if depth <= 0 or not papers:
        return None, []
    read: list[tuple[FullText, str, str]] = []
    for paper in papers[:depth]:
        found = read_paper(handles.html, paper.arxiv_id, paper.title, handles.fetch)
        if found is not None and found.sections:
            read.append((found, str(paper.date.year), paper.abstract))
    if not read:
        LOG.info("no full text landed for any of the top %d papers", depth)
        return None, []
    made = design(
        handles.model,
        question,
        [(p.title, p.abstract) for p in papers[:SAMPLES]],
    )
    rows = merge(extract(handles.model, made, read))
    return repair(handles.model, made, rows), rows


def trim(found: Mined, hard: Effort) -> Mined:
    """
    Cuts what was mined to what this effort prints, since the walk finds hundreds of paths

    Args:
        found: Everything the miner returned.
        hard: The preset.

    Returns:
        The same result, cut.
    """
    return found.model_copy(
        update={
            "magnets": found.magnets[: hard.magnets],
            "lineages": [line for line in found.lineages if len(line.nodes) > 1][: hard.lineages],
            "disputes": found.disputes[: hard.disputes],
            "successors": found.successors[: hard.successors],
            "connectors": found.connectors[: hard.magnets],
        }
    )


def focus(miner: Miner, found: Mined, papers: list[Paper], close: dict[str, float]) -> Mined:
    """
    Holds the disagreements and the successors to the papers the run kept

    A backbone every field cites otherwise fills both, from papers that never touch the question.

    Args:
        miner: The miner that found it, whose dispute picking is reused.
        found: Everything the miner returned, before any cut.
        papers: What the run kept.
        close: Each kept paper's cosine to the question.

    Returns:
        The same result with only kept papers' critiques and only successors near the question.
    """
    kept = {p.arxiv_id for p in papers}
    weight = {m.node: m.weight for m in found.magnets}
    disputes = miner.disputes(found.edges, weight, ("critiques",), kept)
    ranked = sorted(close.get(a, 0.0) for a in kept)
    floor = ranked[int(len(ranked) * FLOOR_SHARE)] if ranked else 0.0
    ahead = [s for s in found.successors if (s.paper.cosine or 0.0) >= floor]
    return found.model_copy(update={"disputes": disputes, "successors": ahead})


def closest(papers: list[Paper], areas: list[Area], close: dict[str, float]) -> list[Paper]:
    """
    The kept papers in the order the method table reads them, seeds first and then the closest

    Args:
        papers: What the run kept, in the order the rankings were made.
        areas: The areas, which name their seeds.
        close: Each kept paper's cosine to the question.

    Returns:
        The same papers, reordered.
    """
    seeds = {a.seed for a in areas if a.seed}
    return sorted(papers, key=lambda p: (p.arxiv_id not in seeds, -close.get(p.arxiv_id, 0.0)))


def as_papers(
    handles: Handles,
    papers: list[Paper],
    grades: dict[str, Any],
    found: Mined,
    cited: set[str],
) -> list[dict[str, Any]]:
    """
    Every paper the run names, with the columns a reader wants and a ranking never needed

    Args:
        handles: The shared handles.
        papers: What the run kept.
        grades: What the reader said about them.
        found: What was mined, which names papers the run kept but never retrieved.
        cited: Which ids the document actually cites.

    Returns:
        One row per paper, the kept ones first.
    """
    successors = {successor.paper.arxiv_id: successor.paper for successor in found.successors}
    named = {m.node for m in found.magnets} | set(found.connectors)
    named |= {n for line in found.lineages for n in line.nodes}
    named |= set(successors)
    every = list(dict.fromkeys([p.arxiv_id for p in papers] + sorted(named)))
    records = read_records(handles.dsn, every)
    kept = {p.arxiv_id: p for p in papers}
    # a paper the walk reached was never retrieved, so its closeness comes off the mining pass
    closeness = {a: p.cosine for a, p in found.papers.items() if p.cosine is not None}
    closeness.update({a: p.cosine for a, p in successors.items() if p.cosine is not None})
    weight = {m.node: m.weight for m in found.magnets}
    out: list[dict[str, Any]] = []
    for arxiv_id in every:
        record = records.get(arxiv_id)
        if record is None:
            continue
        held = kept.get(arxiv_id)
        grade = grades.get(arxiv_id)
        out.append(
            {
                "arxiv_id": arxiv_id,
                "title": record["title"],
                "authors": record["authors"],
                "abstract": record["abstract"],
                "date": record["date"],
                "year": record["date"][:4],
                "category": record["category"],
                "topic": record["topic"],
                "topic_id": record["topic_id"],
                "role": grade.role
                if grade is not None
                else "successor"
                if arxiv_id in successors
                else "",
                "relevance": grade.relevance if grade is not None else None,
                "cosine": (
                    round(held.cosine, 4)
                    if held is not None and held.cosine
                    else round(closeness[arxiv_id], 4)
                    if arxiv_id in closeness
                    else None
                ),
                "magnet": round(weight[arxiv_id], 3) if arxiv_id in weight else None,
                "retrieved": arxiv_id in kept,
                "cited": arxiv_id in cited,
            }
        )
    return out


def as_graph(found: Mined, papers: list[dict[str, Any]], graph: GraphExport) -> dict[str, Any]:
    """
    Every paper the run holds, placed by date and closeness, with the citations between them

    A lineage edge is flagged rather than drawn separately, so one picture carries both the field
    and the paths through it.

    Args:
        found: What was mined.
        papers: The rows written to papers.json, which decide what is plotted.
        graph: The citation graph export, which carries how often each paper is cited.

    Returns:
        The nodes, the edges and which lineage each node sits on.
    """
    weight = {m.node: m.weight for m in found.magnets}
    lines: dict[str, list[int]] = {}
    walked: set[tuple[str, str]] = set()
    for spot, line in enumerate(found.lineages, 1):
        for step, node in enumerate(line.nodes):
            lines.setdefault(node, []).append(spot)
            if step:
                walked.add((line.nodes[step - 1], node))
                walked.add((node, line.nodes[step - 1]))
    counts = graph.get_citation_counts()
    held = {p["arxiv_id"]: p for p in papers}

    def cited_by(arxiv_id: str) -> int:
        row = graph.index.get(arxiv_id)
        return 0 if row is None else int(counts[row])

    nodes = [
        {
            "arxiv_id": p["arxiv_id"],
            "title": p["title"],
            "date": p["date"],
            "role": p["role"] or ("connector" if not p["retrieved"] else "ungraded"),
            "cosine": p["cosine"],
            "magnet": round(weight.get(p["arxiv_id"], 0.0), 3),
            "cited_by": cited_by(p["arxiv_id"]),
            "lines": sorted(set(lines.get(p["arxiv_id"], []))),
            "retrieved": p["retrieved"],
        }
        for p in papers
    ]
    edges = [
        {
            "source": e.source,
            "target": e.target,
            "intent": e.intent,
            "intent_score": e.intent_score,
            "sentence": e.sentence[:SENTENCE_CHARS],
            "walked": (e.source, e.target) in walked,
        }
        for e in found.edges
        if e.source in held and e.target in held
    ]
    seen: set[tuple[str, str, str]] = set()
    kept: list[dict[str, Any]] = []
    for edge in edges:
        key = (str(edge["source"]), str(edge["target"]), str(edge["intent"]))
        if key in seen:
            continue
        seen.add(key)
        kept.append(edge)
    return {"nodes": nodes, "edges": kept}


def open_questions(handles: Handles, areas: list[Area], papers: list[Paper], depth: int) -> None:
    """
    Fills each area with what its own papers say they did not solve

    Args:
        handles: The shared handles.
        areas: The areas, written in place.
        papers: Every paper the run kept.
        depth: How many papers of each area to read.
    """
    held = {p.arxiv_id: p for p in papers}
    for area in areas:
        sections: list[tuple[str, str, str]] = []
        for arxiv_id in area.arxiv_ids[:depth]:
            found = read_open(handles.html, arxiv_id, fetch=handles.fetch)
            for name, body in found[:2]:
                sections.append((arxiv_id, name, body))
        area.unanswered = unanswered(handles.model, area.question or "", sections)
        LOG.info("%s: %d open questions", area.question[:40], len(area.unanswered))
    _ = held


def between(nodes: list[str], edges: list[Edge]) -> list[dict[str, Any]]:
    """
    The citations among one line's papers, once per citing pair and intent

    Args:
        nodes: The line's papers.
        edges: Every edge that was mined, one per occurrence in the text.

    Returns:
        One entry per pair and intent, carrying the first sentence found for it.
    """
    held = set(nodes)
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in edges:
        key = (e.source, e.target, e.intent)
        if e.source in held and e.target in held and key not in out:
            out[key] = {
                "source": e.source,
                "target": e.target,
                "intent": e.intent,
                "intent_score": e.intent_score,
                "sentence": e.sentence[:SENTENCE_CHARS],
            }
    return list(out.values())


def as_report(draft: Draft, found: Mined) -> dict[str, Any]:
    """
    The document as the parts a reader navigates, rather than as one page to scroll

    Args:
        draft: What the document was built from.
        found: What was mined.

    Returns:
        One entry per section the dashboard draws.
    """
    made = draft.design
    return {
        "answer": ground.linkify(draft.answer),
        "opening": next((s.body for s in draft.written if s.title == "What this is about"), ""),
        "claims": [
            {"title": s.title, "body": s.body}
            for s in draft.written
            if s.title != "What this is about"
        ],
        "methods": {
            "table": render(draft.design, draft.methods) if draft.design else "",
            "spread": spread(draft.design, draft.methods) if draft.design else "",
            "gaps": gaps(draft.design, draft.methods) if draft.design else "",
            "columns": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "description": c.description,
                    "options": list(c.options),
                }
                for c in (made.columns if made else ())
            ],
            "rows": [
                {"name": m.name, "year": m.year, "values": m.values, "papers": m.papers}
                for m in draft.methods
            ],
        },
        "areas": [
            {
                "question": a.question,
                "seed": a.seed,
                "papers": a.arxiv_ids,
                "unanswered": a.unanswered,
            }
            for a in draft.areas
        ],
        "successors": [
            {
                "arxiv_id": s.paper.arxiv_id,
                "date": s.paper.date.isoformat(),
                "title": " ".join(s.paper.title.split()),
                "reach": s.reach,
                "intents": sorted(set(s.targets.values())),
                "sentence": s.sentences[0][:400] if s.sentences else "",
            }
            for s in found.successors
        ],
        "disputes": [
            {
                "arxiv_id": e.target,
                "by": e.source,
                "intent": e.intent,
                "sentence": e.sentence[:400],
            }
            for e in found.disputes
        ],
        "lineages": [
            {
                "name": named.name,
                "description": named.description,
                "runs": line.runs,
                "papers": [
                    {
                        "arxiv_id": n,
                        "date": found.papers[n].date.isoformat(),
                        "title": " ".join(found.papers[n].title.split()),
                    }
                    for n in line.nodes
                    if n in found.papers
                ],
                "intents": inside(line.nodes, found.edges),
                "edges": between(line.nodes, found.edges),
            }
            for line, named in zip(
                found.lineages,
                draft.names + [LineName()] * (len(found.lineages) - len(draft.names)),
                strict=True,
            )
        ],
    }


def as_sections(sections: list[dict[str, str] | str] | str | None) -> list[dict[str, str]]:
    """
    The caller's sections as titles and bodies, whichever shape they arrived in

    A markdown string is cut at each heading, so one block of prose becomes its sections.

    Args:
        sections: Dicts with a title and a body, markdown strings, or one markdown string.

    Returns:
        One title and body per section.
    """
    raw = [sections] if isinstance(sections, str) else list(sections or [])
    out: list[dict[str, str]] = []
    for one in raw:
        if isinstance(one, dict):
            out.append({"title": str(one.get("title", "")), "body": str(one.get("body", ""))})
            continue
        for chunk in re.split(r"(?m)^(?=#{1,3} )", str(one)):
            lines = chunk.strip().splitlines()
            if not lines:
                continue
            heading = lines[0].startswith("#")
            out.append(
                {
                    "title": lines[0].lstrip("#").strip() if heading else "",
                    "body": "\n".join(lines[1:] if heading else lines).strip(),
                }
            )
    return out


def write_report(
    handles: Handles,
    query_ids: list[str],
    title: str = "",
    sections: list[dict[str, str] | str] | str | None = None,
    effort: str = "standard",
    end: bool = True,
    question: str = "",
) -> str:
    """
    The whole document, written to disk and returned

    Args:
        handles: The shared handles.
        query_ids: The retrievals this report is built from.
        title: What to call it, defaulting to the question.
        sections: The caller's own prose, as titles and bodies or as markdown.
        effort: quick, standard or deep, which decides how many papers are read in full.
        end: Forget every ranking afterwards, which is what closes a session.
        question: What the report is mined, written and answered against, defaulting to the title.

    Returns:
        The markdown, where it was written and what the guard had to change, as json.
    """
    clock = time.perf_counter()
    _progress(handles, "mining")
    hard = level(effort)
    papers, areas, grades, first, mode, asked, spent = gather(query_ids)
    if not papers:
        named_areas = [q for q in query_ids if get_area(q) is not None]
        if named_areas:
            return json.dumps(
                {
                    "error": "these are area_ids, not query_ids: call retrieve with each"
                    " area_id first"
                    " and pass the query_id it returns",
                    "area_ids": named_areas,
                }
            )
        return json.dumps({"error": "no ranking under those ids, call retrieve first"})

    # each area rewords the question, so the report is held to the one the caller named
    named = " ".join(title.split())
    question = " ".join(question.split()) or named or first
    vector = handles.embed(question)
    miner = Miner(handles.dsn, handles.graph, read_recipe(handles.recipe(mode)))
    pinned = all(held.pinned for q in query_ids if (held := get(q)) is not None)
    mined = miner.mine(papers, vector, asked, expand=not pinned)
    close = read_cosines(handles.dsn, vector, [p.arxiv_id for p in papers])
    found = trim(focus(miner, mined, papers, close), hard)
    _progress(handles, "reading_papers")
    made, methods = table(handles, question, closest(papers, areas, close), hard.full_text)
    told = [
        Section(title=str(s.get("title", "")), body=str(s.get("body", "")))
        for s in as_sections(sections)
        if str(s.get("body", "")).strip()
    ]
    if not told and hard.compose:
        _progress(handles, "composing_report")
        told = compose(handles.model, question, asked, papers, grades, found, made, methods)
    if hard.compose:
        open_questions(handles, areas, papers, OPEN_PAPERS)
    evidence = "\n\n".join(f"## {one.title}\n\n{one.body}" for one in told) or digest(
        question, papers, grades, found, made, methods
    )
    allowed = {p.arxiv_id for p in papers} | set(found.papers)
    short = ground.check(
        handles.dsn,
        ground.mark(answer(handles.model, question, asked, evidence[:EVIDENCE_CHARS])),
        allowed,
    ).text
    told = [
        Section(
            title=one.title,
            body=ground.check(handles.dsn, ground.mark(one.body), allowed).text,
        )
        for one in told
    ]
    draft = Draft(
        question=named or question,
        asked=asked,
        papers=papers,
        areas=areas,
        grades=grades,
        mined=found,
        design=made,
        methods=methods,
        written=told,
        answer=short,
        names=name_lines(handles.model, question, found),
        counts={"queries": len(query_ids), "papers": len(papers)},
        seconds={
            "retrieve and read": round(spent, 1),
            "mine and write": round(time.perf_counter() - clock, 1),
        },
    )
    text = document(draft)

    checked = ground.check(handles.dsn, text, allowed)
    body = ground.linkify(checked.text)
    citation_sentences = getattr(handles, "citation_sentences", True)
    if not citation_sentences:
        body += f"\n## Evidence availability\n\n{MISSING_CITATION_TEXT}\n"
    discussed = ground.read_ids("\n\n".join([short] + [one.body for one in told]))

    where = handles.runs / slug(draft.question, asked)
    where.mkdir(parents=True, exist_ok=True)
    _ = (where / "report.md").write_text(body, encoding="utf-8")
    rows = as_papers(handles, papers, grades, found, discussed or set(checked.held))
    _ = (where / "papers.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    _ = (where / "graph.json").write_text(
        json.dumps(as_graph(found, rows, handles.graph), indent=2), encoding="utf-8"
    )
    features = {"citation_sentences": citation_sentences, "jit_intent_mapping": False}
    degraded = [] if citation_sentences else ["citation_quotations", "sentence_based_disputes"]
    payload = as_report(draft, found) | {
        "evidence_availability": features,
        "degraded_features": degraded,
        "evidence_note": "" if citation_sentences else MISSING_CITATION_TEXT,
    }
    _ = (where / "report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    metric_callback = getattr(handles, "execution_metrics", None)
    _ = (where / "run.json").write_text(
        json.dumps(
            {
                "question": draft.question,
                "asked": asked.isoformat(),
                "mode": mode,
                "effort": hard.name,
                "queries": query_ids,
                "papers": [p.arxiv_id for p in papers],
                "cited": sorted(discussed or set(checked.held)),
                "areas": [
                    {"question": a.question, "seed": a.seed, "papers": a.arxiv_ids} for a in areas
                ],
                "counts": mined.counts,
                "seconds": draft.seconds,
                "corrected": checked.fixed,
                "cut": checked.cut,
                "corpus": getattr(handles, "corpus_info", {}),
                "evidence_availability": features,
                "degraded_features": degraded,
                "execution_metrics": metric_callback() if metric_callback else {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_store = getattr(handles, "report_store", None)
    if report_store is not None:
        _progress(handles, "publishing_report")
        report_store.save_directory(where)
    if end:
        reset()
    LOG.info("wrote %s, %d papers, %d characters", where, len(papers), len(body))
    return json.dumps(
        {
            "path": str(where / "report.md"),
            "papers": len(papers),
            "answer": short,
            "corrected": checked.fixed,
            "cut": checked.cut,
            "report": body,
            "counts": mined.counts,
            "seconds": draft.seconds,
            "degraded_features": degraded,
        },
        indent=2,
    )
