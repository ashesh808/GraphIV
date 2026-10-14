"""
A table whose rows are methods rather than papers, with columns the question decides

A column carrying a closed vocabulary is what makes the table groupable
An empty cell of the cross product between two such columns is a combination nobody published
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.core import llm
from src.report.fulltext import METHOD, RESULT, FullText

LOG = logging.getLogger(__name__)

MAX_COLUMNS = 6
MIN_CHOICE = 2
MAX_OPTIONS = 7
OPTION_CHARS = 24
OTHER_SHARE = 0.4
CELL_WORDS = 8
METHOD_CHARS = 3000
RESULT_CHARS = 2200
ABSTRACT_CHARS = 900
TABLE_CHARS = 2400

NAME = re.compile(r"[^a-z0-9_]")
# a paper calling its contribution "our method" has not named it, so the row would not merge
GENERIC = re.compile(r"^(n/a|none|our |the |this |proposed|a novel|method$|approach$|model$)")

DESIGN = """A researcher asked this.

{question}

These are the papers at the leading edge of that question.

{samples}

Design the columns of one table that compares the METHODS in these papers side by side.

Rules:
- {low} to {high} columns, each with a short snake_case name and a description of at most 8 words.
- At least {choices} columns must be of kind "choice": an axis on which methods genuinely differ,
  with 2 to {options} short option words naming the possible answers.
- A choice column is the point of the table, so pick axes a reader would sort or group the field
  by, the way "dense, sparse, hybrid" splits retrieval.
- The options of a choice column must cover every paper above between them, so one of them has to
  be the plain or default answer that a method doing nothing special on that axis would give.
- Keep every option to three words or fewer.
- One choice column must be the axis the researcher's own question turns on, so that reading that
  column top to bottom answers what they asked.
- Exactly one column of kind "value": the headline number and the benchmark it was measured on.
- Any remaining column is kind "text": one short phrase.
- Name no column whose answer would be the same for every method here.

Reply with json only, no preamble:
{{"columns": [{{"name": "retrieval_type", "kind": "choice", "description": "how candidates are
found", "options": ["dense", "sparse", "hybrid", "graph"]}}]}}
"""

EXTRACT = """A researcher asked this.

{question}

Below is one paper, in its own words.

TITLE: {title}

{body}

Name the method this paper contributes, which is the one it is titled after, then describe it on
the axes below.
Name a second only when the paper introduces two genuinely different methods, never when the
second is an ablation, a setting or a variant of the first.

{columns}

Rules:
- "name" is what the authors call it, the short name another paper would cite it by.
- Never name a baseline, a dataset or someone else's method. Only what this paper introduces.
- A choice axis must be answered with one of its listed options. When none fits, answer in two
  words of your own naming what this method actually does on that axis, never the word "other".
- Write "n/a" for anything the text above does not say. Never guess and never use outside
  knowledge.
- At most {words} words per answer.

Reply with json only, no preamble:
{{"methods": [{{"name": "...", {shape}}}]}}
"""

REPAIR = """These are answers given on one axis of a comparison table that did not match any of its
options.

AXIS: {name}, {description}
OPTIONS: {options}

THE ANSWERS THAT DID NOT MATCH:
{misses}

Name up to {room} more options that would catch most of those answers, in the same style and no
longer than three words each.
Name none at all when the answers have nothing in common.

Reply with json only, no preamble:
{{"options": ["..."]}}
"""


@dataclass(frozen=True)
class Column:
    """
    One axis of the table, which is closed when it carries options
    """

    name: str
    kind: str
    description: str
    options: tuple[str, ...] = ()

    @property
    def closed(self) -> bool:
        """
        Whether the column groups, which only a choice column with options does

        Returns:
            True when the column can be cross tabulated.
        """
        return self.kind == "choice" and len(self.options) >= 2


@dataclass(frozen=True)
class Design:
    """
    The columns chosen for one question
    """

    question: str
    columns: tuple[Column, ...] = ()

    @property
    def names(self) -> list[str]:
        """
        Every column name in order

        Returns:
            The names.
        """
        return [c.name for c in self.columns]

    @property
    def closed(self) -> list[Column]:
        """
        The columns a gap can be read off

        Returns:
            The closed columns.
        """
        return [c for c in self.columns if c.closed]

    @property
    def listing(self) -> str:
        """
        The columns as the extracting prompt sees them

        Returns:
            One line per column, with its options where it has them.
        """
        lines: list[str] = []
        for one in self.columns:
            if one.options:
                tail = f" One of: {', '.join(one.options)}."
            elif one.kind == "value":
                tail = " Give the number and what it was measured on, never the metric name alone."
            else:
                tail = ""
            lines.append(f"- {one.name}: {one.description}.{tail}")
        return "\n".join(lines)

    @property
    def shape(self) -> str:
        """
        The json keys the extracting prompt asks back for

        Returns:
            The key list as a json fragment.
        """
        return ", ".join(f'"{c.name}": "..."' for c in self.columns)


@dataclass
class Method:
    """
    One row of the table, which one or more papers may carry
    """

    name: str
    values: dict[str, str] = field(default_factory=dict)
    papers: list[str] = field(default_factory=list)
    year: str = ""

    @property
    def key(self) -> str:
        """
        What two spellings of one method agree on

        Returns:
            The normalized name.
        """
        return re.sub(r"[^a-z0-9]", "", self.name.lower())[:18]


def design(model: llm.Gemma, question: str, samples: list[tuple[str, str]]) -> Design:
    """
    The model picks the axes this question wants compared, most of them closed

    Args:
        model: The router client.
        question: What was asked.
        samples: Title and abstract of the papers the table will hold.

    Returns:
        The design, which falls back to nothing when the reply does not parse.
    """
    body = "\n\n".join(f"{t}\n{a[:ABSTRACT_CHARS]}" for t, a in samples)
    prompt = DESIGN.format(
        question=question,
        samples=body,
        low=MIN_CHOICE + 2,
        high=MAX_COLUMNS,
        choices=MIN_CHOICE,
        options=MAX_OPTIONS,
    )
    parsed = llm.parse_json(model.ask(prompt, max_tokens=900))
    entries = parsed.get("columns") if isinstance(parsed, dict) else None
    columns: list[Column] = []
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = NAME.sub("_", str(entry.get("name", "")).strip().lower()).strip("_")
            kind = str(entry.get("kind", "text")).strip().lower()
            if not name or kind not in ("choice", "value", "text"):
                continue
            raw = entry.get("options")
            options = tuple(
                " ".join(str(o).split())[:OPTION_CHARS].lower()
                for o in (raw if isinstance(raw, list) else [])
            )[:MAX_OPTIONS]
            said = " ".join(str(entry.get("description", "")).split())[:60]
            columns.append(Column(name, kind, said, options))
    LOG.info("designed %d columns, %d closed", len(columns), sum(1 for c in columns if c.closed))
    return Design(question, tuple(columns[:MAX_COLUMNS]))


def snap(column: Column, got: str) -> str:
    """
    Pulls an answer onto one of a closed column's options where it names one

    A model that answers "dense retrieval" on a dense or sparse axis has answered dense.

    Args:
        column: The column the answer belongs to.
        got: What the model said.

    Returns:
        The option, or what was said when nothing matches.
    """
    if not column.closed or not got:
        return got
    low = got.lower()
    for option in column.options:
        if low == option or low.startswith(option) or option in low.split():
            return option
    return got


def body(paper: FullText, summary: str) -> str:
    """
    What the extracting prompt reads, which is the method and the results in the paper's own words

    Args:
        paper: The parsed paper.
        summary: Its abstract, which is all a run with no full text has.

    Returns:
        The body, falling back to the abstract when no section matched.
    """
    found = paper.pick(METHOD)[:METHOD_CHARS]
    result = paper.pick(RESULT)[:RESULT_CHARS]
    parts = [f"ABSTRACT\n{summary[:ABSTRACT_CHARS]}"]
    if found:
        parts.append(f"METHOD\n{found}")
    if result:
        parts.append(f"RESULTS\n{result}")
    room = TABLE_CHARS
    for table in paper.result_tables[:3]:
        drawn = table.render()[:room]
        if not drawn:
            break
        parts.append(f"TABLE\n{drawn}")
        room -= len(drawn)
        if room <= 0:
            break
    return "\n\n".join(parts)


def extract(
    model: llm.Gemma, made: Design, papers: list[tuple[FullText, str, str]]
) -> list[Method]:
    """
    Every method each paper contributes, described on the designed axes

    Args:
        model: The router client.
        made: The columns.
        papers: The parsed paper, its publication year and its abstract.

    Returns:
        One entry per method per paper, before merging.
    """
    if not made.columns or not papers:
        return []
    prompts = [
        EXTRACT.format(
            question=made.question,
            title=paper.title,
            body=body(paper, summary),
            columns=made.listing,
            shape=made.shape,
            words=CELL_WORDS,
        )
        for paper, _, summary in papers
    ]
    replies = model.ask_many(prompts, max_tokens=700)
    out: list[Method] = []
    for (paper, year, _), reply in zip(papers, replies, strict=True):
        parsed = llm.parse_json(reply)
        entries = parsed.get("methods") if isinstance(parsed, dict) else None
        if not isinstance(entries, list):
            continue
        for entry in entries[:2]:
            if not isinstance(entry, dict):
                continue
            name = " ".join(str(entry.get("name", "")).split())[:34]
            if not name or GENERIC.match(name.lower()):
                continue
            values = {
                c.name: snap(c, " ".join(str(entry.get(c.name, "n/a")).split())[:70])
                for c in made.columns
            }
            out.append(Method(name=name, values=values, papers=[paper.arxiv_id], year=year))
    LOG.info("extracted %d methods from %d papers", len(out), len(papers))
    return out


def merge(found: list[Method]) -> list[Method]:
    """
    One row per method, since two papers describing one method are one row

    Args:
        found: Every extracted method.

    Returns:
        The merged rows, newest first.
    """
    out: dict[str, Method] = {}
    for one in found:
        held = out.get(one.key)
        if held is None:
            out[one.key] = one
            continue
        held.papers.extend(p for p in one.papers if p not in held.papers)
        for name, value in one.values.items():
            if held.values.get(name, "n/a") in ("", "n/a") and value not in ("", "n/a"):
                held.values[name] = value
        held.year = max(held.year, one.year)
    return sorted(out.values(), key=lambda m: (m.year, m.name), reverse=True)


def repair(model: llm.Gemma, made: Design, rows: list[Method]) -> Design:
    """
    Widens a closed column whose options missed most of the field, then the rows re-snap onto it

    An axis answered off its own options by half the table is not an axis, and the cheap repair is
    to read what was actually said rather than to extract again.

    Args:
        model: The router client.
        made: The design as proposed.
        rows: The extracted methods, whose unmatched answers are the evidence.

    Returns:
        The design, unchanged where nothing missed.
    """
    if not rows:
        return made
    out: list[Column] = []
    for column in made.columns:
        missed = [
            one.values.get(column.name, "")
            for one in rows
            if column.closed
            and one.values.get(column.name, "n/a") not in column.options
            and one.values.get(column.name, "n/a") not in ("", "n/a", "other")
        ]
        room = MAX_OPTIONS - len(column.options)
        if not column.closed or len(missed) < OTHER_SHARE * len(rows) or room <= 0:
            out.append(column)
            continue
        prompt = REPAIR.format(
            name=column.name,
            description=column.description,
            options=", ".join(column.options),
            misses="\n".join(f"- {m}" for m in missed[:30]),
            room=room,
        )
        parsed = llm.parse_json(model.ask(prompt, max_tokens=200))
        more = parsed.get("options") if isinstance(parsed, dict) else None
        extra = tuple(
            " ".join(str(o).split())[:OPTION_CHARS].lower()
            for o in (more if isinstance(more, list) else [])
            if str(o).strip()
        )[:room]
        LOG.info("%s missed %d of %d, added %s", column.name, len(missed), len(rows), extra or "()")
        out.append(Column(column.name, column.kind, column.description, column.options + extra))
    made = Design(made.question, tuple(out))
    for one in rows:
        for column in made.columns:
            one.values[column.name] = snap(column, one.values.get(column.name, "n/a"))
    return made


def render(made: Design, rows: list[Method]) -> str:
    """
    The method table, one row per method with the papers that carry it

    Args:
        made: The columns.
        rows: The merged methods.

    Returns:
        The markdown table, empty when nothing was extracted.
    """
    if not made.columns or not rows:
        return ""
    head = ["method", "year", *made.names, "papers"]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    for one in rows:
        cites = " ".join(f"[`{a}`](https://arxiv.org/abs/{a})" for a in one.papers[:2])
        cells = [one.name, one.year, *[one.values.get(c, "n/a") for c in made.names], cites]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def spread(made: Design, rows: list[Method]) -> str:
    """
    How the methods fall along each closed axis, which is what people are doing

    Args:
        made: The columns.
        rows: The merged methods.

    Returns:
        One table per closed column.
    """
    out: list[str] = []
    for column in made.closed:
        counts = {option: 0 for option in column.options}
        other = 0
        for one in rows:
            got = one.values.get(column.name, "n/a")
            if got in counts:
                counts[got] += 1
            elif got not in ("", "n/a"):
                other += 1
        out.append(f"**{column.name}**, {column.description}\n")
        out.append("| option | methods |")
        out.append("| --- | --- |")
        for option, many in sorted(counts.items(), key=lambda kv: -kv[1]):
            out.append(f"| {option} | {many} |")
        if other:
            out.append(f"| something else | {other} |")
        out.append("")
    return "\n".join(out)


def gaps(made: Design, rows: list[Method], thin: int = 0) -> str:
    """
    The cross product of two closed axes, where an empty cell is a combination nobody published

    Args:
        made: The columns.
        rows: The merged methods.
        thin: The count at or below which a cell counts as a gap.

    Returns:
        One cross tabulation per pair of closed columns, and the empty cells named under it.
    """
    closed = made.closed
    if len(closed) < 2 or not rows:
        return ""
    out: list[str] = []
    for spot, left in enumerate(closed):
        for right in closed[spot + 1 :]:
            grid = {(a, b): 0 for a in left.options for b in right.options}
            for one in rows:
                mark = (one.values.get(left.name, ""), one.values.get(right.name, ""))
                if mark in grid:
                    grid[mark] += 1
            if not any(grid.values()):
                continue
            out.append(f"**{left.name} against {right.name}**\n")
            out.append("| | " + " | ".join(right.options) + " |")
            out.append("| --- |" + " --- |" * len(right.options))
            for a in left.options:
                cells = " | ".join(str(grid[(a, b)]) for b in right.options)
                out.append(f"| {a} | {cells} |")
            # a cell is only a gap when both of its options were each used somewhere
            used = {(a, b) for (a, b), n in grid.items() if n}
            lefts, rights = {a for a, _ in used}, {b for _, b in used}
            empty = [
                f"{a} + {b}"
                for (a, b), n in grid.items()
                if n <= thin and a in lefts and b in rights
            ]
            if empty:
                out.append("")
                out.append(f"Nobody here does: {', '.join(sorted(empty))}.")
            out.append("")
    return "\n".join(out)
