"""
The written half of a report: an outline over the evidence, then one call per section

A single call self-limits to about a thousand words however much evidence it is given
The digest is a node table plus an adjacency list grouped by intent, which is what a writer reads
"""

from __future__ import annotations

import logging
from datetime import date

from src.core import llm
from src.core.schema import Grade, Paper
from src.miner.miner import Mined
from src.report.render import LineName, Section, inside
from src.report.table import Design, Method, render

LOG = logging.getLogger(__name__)

ABSTRACT_CHARS = 420
SENTENCE_CHARS = 240
MAX_SECTIONS = 6
MIN_SECTIONS = 3
# asking the outline to cover every kept paper ran it past its budget at 120 papers
SECTION_IDS = 8
# five sections with their ids and a sentence each runs past a shorter budget and parses as nothing
OUTLINE_TOKENS = 1800
SECTION_TOKENS = 1400
CLOSE_TOKENS = 900
ANSWER_TOKENS = 900
NAME_TOKENS = 900
OPEN_TOKENS = 700
OPEN_CHARS = 1600
OPEN_PAPERS = 10

OUTLINE = """A researcher asked this.

{question}

Below is everything that was retrieved for it, as of {asked}.

{digest}

Plan the sections of a literature review answering that question.

Rules:
- Between {low} and {high} sections, ordered so a reader who knows nothing can follow.
- A section is a claim about the field, not a category. "Rule-based forecasters trade accuracy
  for an audit trail" is a section. "Rule-based methods" is not.
- Keep every title under 12 words and every point to one short sentence.
- Give each section the arXiv ids it has to discuss, from the list above and nowhere else.
- Every id appears in at most one section, and a section lists at most {per} ids, the ones it
  cannot be written without.
- The last section is what is unresolved, drawn from the disputes and the open questions above.

Reply with json only, no preamble:
{{"sections": [{{"title": "...", "ids": ["2401.00001"], "point": "one sentence"}}]}}
"""

SECTION = """You are writing one section of a literature review answering this question.

{question}

This is the evidence for the whole review.

{digest}

Write the section titled "{title}".
Its point is: {point}
It must discuss these papers: {ids}

Rules:
- Start with "## {title}" and write prose. No bullet lists and no headings below this one.
- Cite every paper you name as arXiv:<id> inline, using only ids from the evidence above.
- Say what each paper did, then what it cost, then what the next one changed about it. A
  sentence that could be written without having read the paper does not belong.
- Where the evidence carries a disagreement, name both sides and say what the argument is about.
- Never invent a number. Quote only numbers the evidence above states.
- Never reconstruct or invent citation quotations. Intent labels are model predictions,
  not verbatim statements; describe a labeled relation as a prediction when no text is supplied.
- 250 to 400 words. Do not summarize the section at its end.
"""

UNANSWERED = """A researcher asked this.

{question}

Below are the limitations, discussion and future work sections of the papers that answer it, in
the authors' own words.

{sections}

Name what this area has not answered yet.

Rules:
- Between 3 and 6 questions, each one sentence, each something a paper above says is open.
- Name the paper that said it as its arXiv id, in brackets at the end.
- Never invent a limitation. If two papers name the same one, say so once and cite both.
- Order them by how often the papers above raise them, most raised first.

Reply with json only, no preamble:
{{"open": ["The evaluation protocol leaks future facts into training [2004.04926]"]}}
"""

CLOSE = """You are writing the opening of a literature review answering this question.

{question}

These are the sections that follow, with the papers each one covers.

{outline}

{digest}

Write two paragraphs, 160 to 240 words, starting with "## {title}".
The first says what this field is trying to do and what makes it hard.
The second says how the answer has moved, naming the papers the lineages run through as
arXiv:<id>, and ends by saying what the sections below settle.
Cite only ids from the evidence. Never invent a number.
"""

ANSWER = """A researcher asked this.

{question}

This is what the review found, as of {asked}.

{evidence}

Answer the question in one sentence of at most 35 words, the TL;DR a reader stops at.

Rules:
- The sentence is the answer itself, not a description of the field or of this review.
- When the question asks two things, the sentence answers both.
- Name the approach that carries the answer rather than listing every approach.
- Cite at most two papers, as arXiv:<id>, using only ids from above.
- Never invent a number, and where the evidence leaves the question open, say that instead.
- No heading, no label and no preamble, only the sentence.
"""

NAME = """A citation walk reproduced this path through a field, oldest paper first.

{question}

{papers}

How the papers on it cite each other: {cites}.

Names already given to other paths through this field: {taken}.

Say what thread of work runs through this path.

Rules:
- The name is at most six plain words a researcher would use, with no arXiv id.
- The description is one or two sentences on what changed from the first paper to the last.
- The name differs from every name already given, by saying what sets this path apart.

Reply with json only, no preamble:
{{"name": "...", "description": "..."}}
"""


def digest(
    question: str,
    papers: list[Paper],
    grades: dict[str, Grade],
    found: Mined | None,
    design: Design | None,
    methods: list[Method],
) -> str:
    """
    Everything a writer is given, as a node table and an adjacency list grouped by intent

    Args:
        question: What was asked.
        papers: What the run kept.
        grades: What the reader said about them.
        found: What was mined, or None when nothing was.
        design: The method table's columns, or None.
        methods: The method table's rows.

    Returns:
        The digest.
    """
    parts = [f"QUESTION: {question}", "", "NODES, the papers this review may cite"]
    if found is not None and found.edges and not any(edge.sentence for edge in found.edges):
        parts += [
            "",
            "EVIDENCE LIMITATION: Citation sentences are unavailable in this corpus. "
            "The citation relations below are precomputed intent classifications, not quotations. "
            "Do not invent or reconstruct wording attributed to a citing paper. "
            "Omit sentence-based dispute claims; summarize the supplied metadata and abstracts.",
        ]
    for paper in papers:
        role = grades[paper.arxiv_id].role if paper.arxiv_id in grades else "ungraded"
        name = " ".join(paper.title.split())
        parts.append(
            f"- {paper.arxiv_id} ({paper.date.isoformat()}) [{role}] {name}"
            f"\n  {paper.abstract[:ABSTRACT_CHARS]}"
        )
    if found is not None:
        held = found.papers
        if found.lineages:
            parts += ["", "LINEAGES, paths the citation walk reproduced, oldest first"]
            for spot, line in enumerate(found.lineages, 1):
                names = " -> ".join(
                    f"{n} ({held[n].date.year}) {' '.join(held[n].title.split())[:50]}"
                    for n in line.nodes
                    if n in held
                )
                parts.append(f"- line {spot}: {names}")
        if found.magnets:
            parts += ["", "ARGUED WITH, the papers this set takes positions on"]
            for magnet in found.magnets[:12]:
                if magnet.node not in held:
                    continue
                counts = ", ".join(f"{k} {v}" for k, v in magnet.argued.items())
                parts.append(
                    f"- {magnet.node} {' '.join(held[magnet.node].title.split())[:60]} ({counts})"
                )
        if found.disputes:
            parts += ["", "DISPUTES, in the words of the paper doing the disputing"]
            for edge in found.disputes[:12]:
                held_title = held[edge.target].title if edge.target in held else ""
                name = " ".join(held_title.split())[:44]
                said = edge.sentence[:SENTENCE_CHARS]
                parts.append(f"- on {edge.target} {name}, {edge.intent}: {said}")
        if found.successors:
            parts += ["", "JUST APPEARED, papers citing this set that are too new to be cited"]
            for one in found.successors[:10]:
                intents = ", ".join(sorted(set(one.targets.values())))
                parts.append(
                    f"- {one.paper.arxiv_id} ({one.paper.date.isoformat()}) "
                    f"{' '.join(one.paper.title.split())[:60]} ({intents}, against {one.reach})"
                )
    if design is not None and methods:
        parts += ["", "THE METHODS SIDE BY SIDE", render(design, methods)]
    return "\n".join(parts)


def unanswered(model: llm.Gemma, question: str, sections: list[tuple[str, str, str]]) -> list[str]:
    """
    What the papers of one area say they did not solve, read off their own limitations sections

    Args:
        model: The router client.
        question: What the area was asked.
        sections: One arXiv id, section title and body per paper that has such a section.

    Returns:
        The open questions, most raised first, empty when nothing parsed.
    """
    if not sections:
        return []
    body = "\n\n".join(f"[{a}] {t}\n{b[:OPEN_CHARS]}" for a, t, b in sections)
    parsed = llm.parse_json(
        model.ask(UNANSWERED.format(question=question, sections=body), max_tokens=OPEN_TOKENS)
    )
    raw = parsed.get("open") if isinstance(parsed, dict) else None
    entries = raw if isinstance(raw, list) else []
    out = [" ".join(str(one).split()) for one in entries if str(one).strip()]
    LOG.info("found %d open questions over %d sections", len(out), len(sections))
    return out[:6]


def outline(
    model: llm.Gemma, question: str, asked: date, body: str
) -> list[tuple[str, list[str], str]]:
    """
    The sections the review is written in, each holding the papers it has to discuss

    Args:
        model: The router client.
        question: What was asked.
        asked: The date the run is capped at.
        body: The digest.

    Returns:
        One title, its ids and its point per section.
    """
    prompt = OUTLINE.format(
        question=question,
        asked=asked.isoformat(),
        digest=body,
        low=MIN_SECTIONS,
        high=MAX_SECTIONS,
        per=SECTION_IDS,
    )
    parsed = llm.parse_json(model.ask(prompt, max_tokens=OUTLINE_TOKENS))
    entries = parsed.get("sections") if isinstance(parsed, dict) else None
    out: list[tuple[str, list[str], str]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        title = " ".join(str(entry.get("title", "")).split())
        ids = [str(i).strip() for i in entry.get("ids", []) if str(i).strip()][:SECTION_IDS]
        point = " ".join(str(entry.get("point", "")).split())
        if title and ids:
            out.append((title, ids, point))
    LOG.info("outlined %d sections", len(out))
    return out[:MAX_SECTIONS]


def compose(
    model: llm.Gemma,
    question: str,
    asked: date,
    papers: list[Paper],
    grades: dict[str, Grade],
    found: Mined | None,
    design: Design | None,
    methods: list[Method],
) -> list[Section]:
    """
    The whole written half, which is an opening and one section per point the outline made

    Args:
        model: The router client.
        question: What was asked.
        asked: The date the run is capped at.
        papers: What the run kept.
        grades: What the reader said about them.
        found: What was mined.
        design: The method table's columns.
        methods: The method table's rows.

    Returns:
        The sections, the opening first, empty when the outline did not parse.
    """
    body = digest(question, papers, grades, found, design, methods)
    plan = outline(model, question, asked, body)
    if not plan:
        return []
    prompts = [
        SECTION.format(question=question, digest=body, title=t, point=p, ids=", ".join(ids))
        for t, ids, p in plan
    ]
    written = model.ask_many(prompts, max_tokens=SECTION_TOKENS)
    listing = "\n".join(f"- {t}: {p} ({', '.join(ids)})" for t, ids, p in plan)
    opening = model.ask(
        CLOSE.format(question=question, outline=listing, digest=body, title="What this is about"),
        max_tokens=CLOSE_TOKENS,
    )
    out = [Section(title="What this is about", body=strip_heading(opening, "What this is about"))]
    for (title, _, _), text in zip(plan, written, strict=True):
        body_text = strip_heading(text, title)
        if body_text:
            out.append(Section(title=title, body=body_text))
    LOG.info("composed %d sections", len(out))
    return [one for one in out if one.body]


def strip_heading(text: str, title: str) -> str:
    """
    The section without the heading the model was told to open with, which the renderer adds back

    Args:
        text: What the model wrote.
        title: The heading it was given.

    Returns:
        The body.
    """
    body = text.strip()
    for opener in (f"## {title}", f"# {title}", title):
        if body.lower().startswith(opener.lower()):
            body = body[len(opener) :].lstrip(" :\n")
            break
    return body.strip()


def answer(model: llm.Gemma, question: str, asked: date, evidence: str) -> str:
    """
    The question answered in one sentence, which the document opens on

    Args:
        model: The router client.
        question: What was asked.
        asked: The date the run is capped at.
        evidence: The written sections when there are any, the digest otherwise.

    Returns:
        The sentence, empty when the model returned nothing.
    """
    reply = model.ask(
        ANSWER.format(question=question, asked=asked.isoformat(), evidence=evidence),
        max_tokens=ANSWER_TOKENS,
    )
    return " ".join(reply.split())


def name_line(
    model: llm.Gemma, question: str, found: Mined, nodes: list[str], taken: list[str]
) -> LineName:
    """
    A name and a description for one lineage, from its papers and how they cite each other

    Args:
        model: The router client.
        question: What was asked.
        found: What was mined, which holds the papers and the edges.
        nodes: The lineage, oldest first.
        taken: The names earlier lines were given, which this one must differ from.

    Returns:
        The name and description, both empty when the reply did not parse.
    """
    held = found.papers
    listing = "\n".join(
        f"- ({held[n].date.year}) {' '.join(held[n].title.split())}" for n in nodes if n in held
    )
    counted = inside(nodes, found.edges)
    cites = ", ".join(f"{n} {intent}" for intent, n in counted.items()) or "none recorded"
    parsed = llm.parse_json(
        model.ask(
            NAME.format(
                question=question,
                papers=listing,
                cites=cites,
                taken="; ".join(taken) or "none yet",
            ),
            max_tokens=NAME_TOKENS,
        )
    )
    if not isinstance(parsed, dict):
        return LineName()
    return LineName(
        name=" ".join(str(parsed.get("name", "")).split()),
        description=" ".join(str(parsed.get("description", "")).split()),
    )


def name_lines(model: llm.Gemma, question: str, found: Mined | None) -> list[LineName]:
    """
    A name and a description per lineage, one call each, every call told the names already given

    Args:
        model: The router client.
        question: What was asked.
        found: What was mined.

    Returns:
        One entry per lineage in order.
    """
    if found is None:
        return []
    named: list[LineName] = []
    for line in found.lineages:
        taken = [n.name for n in named if n.name]
        named.append(name_line(model, question, found, line.nodes, taken))
    LOG.info("named %d of %d lines", sum(1 for n in named if n.name), len(named))
    return named
