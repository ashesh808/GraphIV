"""
The document a researcher reads, assembled from what was mined and what the caller wrote

Every section is evidence the caller can check, so the prose it writes sits beside the papers
A section with nothing behind it is left out rather than printed empty
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from pydantic import BaseModel, Field

from src.core.schema import Edge, Grade, Paper
from src.miner.miner import Mined
from src.report.table import Design, Method, gaps, render, spread

ROLES = ("foundational", "core", "frontier", "survey", "adjacent", "unrelated")
SENTENCE_CHARS = 300
TITLE_CHARS = 90


class Section(BaseModel):
    """
    One stretch of prose the caller wrote, which the document carries as it was written
    """

    title: str
    body: str


class Area(BaseModel):
    """
    One question the report answers, the papers that came back for it and what they left open
    """

    question: str
    arxiv_ids: list[str] = Field(default_factory=list)
    unanswered: list[str] = Field(default_factory=list)


class LineName(BaseModel):
    """
    What one lineage is about, in a few words and then in a sentence or two
    """

    name: str = ""
    description: str = ""


class Draft(BaseModel):
    """
    Everything one document is built from, none of which it computes itself
    """

    question: str
    asked: date
    papers: list[Paper] = Field(default_factory=list)
    areas: list[Area] = Field(default_factory=list)
    grades: dict[str, Grade] = Field(default_factory=dict)
    mined: Mined | None = None
    design: Design | None = None
    methods: list[Method] = Field(default_factory=list)
    written: list[Section] = Field(default_factory=list)
    answer: str = ""
    names: list[LineName] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    seconds: dict[str, float] = Field(default_factory=dict)


def link(arxiv_id: str) -> str:
    """
    One arXiv id as the link every section uses

    Args:
        arxiv_id: The paper.

    Returns:
        The markdown link.
    """
    return f"[`{arxiv_id}`](https://arxiv.org/abs/{arxiv_id})"


def clean(title: str) -> str:
    """
    One title on one line, short enough that a list of thirty stays readable

    Args:
        title: The raw title, which carries the line breaks the source metadata had.

    Returns:
        The cleaned title.
    """
    return " ".join(title.split())[:TITLE_CHARS]


def head(draft: Draft) -> str:
    """
    The title line and what the run cost

    Args:
        draft: What the document is built from.

    Returns:
        The heading.
    """
    total = sum(draft.seconds.values())
    spent = f" in {total:.0f} seconds" if total else ""
    return f"# {draft.question}\n\nAnswered as of {draft.asked.isoformat()}{spent}."


def short(draft: Draft) -> str:
    """
    The question answered in one sentence, set apart so it reads before anything else

    Args:
        draft: What the document is built from.

    Returns:
        The quoted paragraph, empty when none was written.
    """
    return f"> **TL;DR.** {draft.answer}" if draft.answer else ""


def state(draft: Draft) -> str:
    """
    What the area currently is, each paper carrying what the reader called it

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when no paper survived.
    """
    if not draft.papers:
        return ""
    held = {p.arxiv_id: p for p in draft.papers}
    areas = draft.areas or [Area(question="", arxiv_ids=list(held))]
    lines = ["## What these areas currently are", ""]
    for area in areas:
        if area.question:
            lines += [f"### {area.question}", ""]
        mine = by_role([held[a] for a in area.arxiv_ids if a in held], draft)
        for spot, paper in enumerate(mine, 1):
            grade = draft.grades.get(paper.arxiv_id)
            role = grade.role if grade is not None else "ungraded"
            lines.append(
                f"{spot}. `{role:12s}` {paper.date.isoformat()} {link(paper.arxiv_id)} "
                f"{clean(paper.title)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def by_role(papers: list[Paper], draft: Draft) -> list[Paper]:
    """
    One area's papers, the work it is built on first and the tangents last

    Args:
        papers: The papers of one area.
        draft: What the document is built from, which carries the grades.

    Returns:
        The reordered papers.
    """
    order = {role: spot for spot, role in enumerate(ROLES)}
    return sorted(
        papers,
        key=lambda p: (
            order.get(draft.grades[p.arxiv_id].role if p.arxiv_id in draft.grades else "", 9),
            -(p.score or 0.0),
        ),
    )


def inside(nodes: list[str], edges: list[Edge]) -> dict[str, int]:
    """
    How the papers of one line cite each other, one count per citing pair and intent

    Args:
        nodes: The line's papers.
        edges: Every edge that was mined.

    Returns:
        A count per intent, the most frequent first.
    """
    held = set(nodes)
    pairs = {(e.source, e.target, e.intent) for e in edges if e.source in held and e.target in held}
    return dict(Counter(intent for _, _, intent in pairs).most_common())


def lineages(draft: Draft) -> str:
    """
    How the area got here, one dated path per line with its name and how its papers cite each other

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when no path reproduced.
    """
    if draft.mined is None or not draft.mined.lineages:
        return ""
    papers = draft.mined.papers
    lines = ["## How it got here", ""]
    for spot, line in enumerate(draft.mined.lineages, 1):
        named = draft.names[spot - 1] if spot <= len(draft.names) else LineName()
        runs = "once" if line.runs == 1 else f"{line.runs} times"
        lines.append(f"### Line {spot}{': ' + named.name if named.name else ''}")
        lines.append("")
        if named.description:
            lines.append(named.description)
            lines.append("")
        counted = inside(line.nodes, draft.mined.edges)
        said = ", ".join(f"{n} {intent}" for intent, n in counted.items())
        lines.append(
            f"{len(line.nodes)} papers, reproduced {runs}"
            + (f", citing each other as {said}." if said else ".")
        )
        lines.append("")
        for node in line.nodes:
            paper = papers.get(node)
            if paper is None:
                continue
            lines.append(f"- {paper.date.isoformat()} {link(node)} {clean(paper.title)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def methods(draft: Draft) -> str:
    """
    The methods side by side, how they spread along each axis, and the combinations nobody published

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when no method was extracted.
    """
    if draft.design is None or not draft.methods:
        return ""
    parts = ["## The methods side by side", "", render(draft.design, draft.methods), ""]
    spreading = spread(draft.design, draft.methods)
    if spreading:
        parts += ["### What people are doing on each axis", "", spreading]
    empty = gaps(draft.design, draft.methods)
    if empty:
        parts += ["### What nobody here has tried", "", empty]
    return "\n".join(parts).rstrip()


def fresh(draft: Draft) -> str:
    """
    What has appeared since and taken a position on the answer, which needs no citations of its own

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when nothing has.
    """
    if draft.mined is None or not draft.mined.successors:
        return ""
    lines = [
        "## What has just appeared against it",
        "",
        "Each of these cites one of the papers above and says it extends, disputes or benchmarks",
        "against it, so none of them needs a citation of its own to be found.",
        "",
    ]
    for one in draft.mined.successors:
        intents = ", ".join(sorted(set(one.targets.values())))
        lines.append(
            f"- {one.paper.date.isoformat()} {link(one.paper.arxiv_id)} "
            f"{clean(one.paper.title)} ({intents}, against {one.reach} of the list)"
        )
        if one.sentences:
            lines.append(f"  > {one.sentences[0][:SENTENCE_CHARS]}")
    return "\n".join(lines)


def unanswered(draft: Draft) -> str:
    """
    What the papers of each area say they did not solve, in their own limitations sections

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when no paper carried such a section.
    """
    held = [a for a in draft.areas if a.unanswered]
    if not held:
        return ""
    lines = ["## What is still unanswered", ""]
    for area in held:
        if area.question:
            lines += [f"### {area.question}", ""]
        lines += [f"- {one}" for one in area.unanswered]
        lines.append("")
    return "\n".join(lines).rstrip()


def argued(draft: Draft) -> str:
    """
    What the field disputes, in the words of the paper doing the disputing

    Args:
        draft: What the document is built from.

    Returns:
        The section, empty when no sentence was labeled.
    """
    if draft.mined is None or not draft.mined.disputes:
        return ""
    papers = draft.mined.papers
    lines = [
        "## Where the field disagrees",
        "",
        "Each of these is one paper telling another it is wrong, in the words it used.",
        "",
    ]
    for edge in draft.mined.disputes:
        target = papers.get(edge.target)
        name = clean(target.title) if target is not None else edge.target
        lines.append(f"- on {link(edge.target)} {name}, {edge.intent}:")
        lines.append(f"  > {edge.sentence[:SENTENCE_CHARS]}")
    return "\n".join(lines)


def written(draft: Draft) -> str:
    """
    Whatever prose the caller wrote, in the order it wrote it

    Args:
        draft: What the document is built from.

    Returns:
        The sections, empty when the caller wrote none.
    """
    return "\n\n".join(f"## {one.title}\n\n{one.body.strip()}" for one in draft.written)


def working(draft: Draft) -> str:
    """
    What the run did, which is how a reader checks the document was not written from nothing

    Args:
        draft: What the document is built from.

    Returns:
        The section.
    """
    counts = dict(draft.counts)
    if draft.mined is not None:
        counts |= draft.mined.counts
    if not counts and not draft.seconds:
        return ""
    lines = ["## The working", "", "| stage | count |", "| --- | --- |"]
    lines += [f"| {name} | {value} |" for name, value in counts.items()]
    if draft.seconds:
        lines += ["", "| stage | seconds |", "| --- | --- |"]
        lines += [f"| {name} | {value:.1f} |" for name, value in draft.seconds.items()]
    return "\n".join(lines)


def document(draft: Draft) -> str:
    """
    The whole report, leaving out every section nothing was found for

    Args:
        draft: What the document is built from.

    Returns:
        The markdown.
    """
    parts = [
        head(draft),
        short(draft),
        written(draft),
        methods(draft),
        state(draft),
        lineages(draft),
        fresh(draft),
        unanswered(draft),
        argued(draft),
        working(draft),
    ]
    return "\n\n".join(p for p in parts if p.strip()) + "\n"
