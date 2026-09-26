"""
Everything readable out of one paper's html, kept as sections and as tables rather than as prose

An abstract caps how much substance a writer can say about a paper
A result table is where every number in a machine learning paper actually lives
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser, LexborNode

from src.core.fetch import html_file

LOG = logging.getLogger(__name__)

METHOD = ("method", "approach", "model", "architecture", "framework", "algorithm", "our ")
RESULT = ("result", "experiment", "evaluation", "benchmark", "comparison", "ablation", "analysis")
OPEN = ("limitation", "future work", "discussion", "conclusion", "broader impact")

SECTION_CHARS = 5000
MIN_SECTION = 200
CELL_CHARS = 40
MAX_ROWS = 30
MIN_NUMBERS = 6

NUMBER = re.compile(r"-?\d+(?:\.\d+)?%?")
MATH = re.compile(r"[_^]\{|\\[a-zA-Z]+")
# mathml renders an operator as its spoken name, which lands in the cell next to the symbol
SPOKEN = re.compile(r"percent|plus-or-minus|times|superscript|subscript")


@dataclass
class Table:
    """
    One table from a paper, flattened to rows of cells
    """

    caption: str
    rows: list[list[str]] = field(default_factory=list)

    @property
    def numbers(self) -> int:
        """
        How many decimal numbers the table holds, which is how a result table is told apart

        Returns:
            The count.
        """
        return len(re.findall(r"\d+\.\d+", " ".join(" ".join(r) for r in self.rows)))

    def render(self) -> str:
        """
        The table as pipe separated text, which is what a model reads

        Returns:
            The caption and the rows.
        """
        body = "\n".join(" | ".join(c for c in row) for row in self.rows[:MAX_ROWS])
        return f"{self.caption}\n{body}" if self.caption else body


@dataclass
class FullText:
    """
    One paper as everything above the abstract sees it
    """

    arxiv_id: str
    title: str
    sections: dict[str, str] = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)

    @property
    def result_tables(self) -> list[Table]:
        """
        The tables carrying enough numbers to be reporting a measurement

        Returns:
            Those tables, most numbers first.
        """
        found = [t for t in self.tables if t.numbers >= MIN_NUMBERS]
        return sorted(found, key=lambda t: -t.numbers)

    def pick(self, words: tuple[str, ...], limit: int = 2) -> str:
        """
        The sections whose titles match any of a set of words

        Args:
            words: What to look for in a section title, lowercased.
            limit: The most sections to join.

        Returns:
            The joined text.
        """
        got = [
            f"## {t}\n{b}" for t, b in self.sections.items() if any(w in t.lower() for w in words)
        ]
        return "\n\n".join(got[:limit])


def read_cell(node: LexborNode) -> str:
    """
    One table cell as text, with the MathML echo of its own number removed

    The renderer writes a number once as text and again as MathML, so the raw text returns it
    twice running, and the LaTeX that survives the second copy is cut with it.

    Args:
        node: The td or th.

    Returns:
        The cleaned text.
    """
    got = " ".join(node.text().split())[:CELL_CHARS]
    bare = got.replace(" ", "")
    half = len(bare) // 2
    if bare and len(bare) % 2 == 0 and bare[:half] == bare[half:]:
        got = bare[:half]
    first = NUMBER.search(got)
    if first is not None:
        again = got.find(first.group(0), first.end())
        if again >= 0:
            got = got[:again].rstrip()
    said = SPOKEN.search(got)
    if said is not None:
        got = got[: said.start()].rstrip()
    cut = MATH.search(got)
    return (got[: cut.start()] if cut is not None else got).strip()


def read_caption(node: LexborNode) -> str:
    """
    The caption belonging to one table, and nothing belonging to a neighbor

    A table sits inside its own figure, so the search stops at the first ancestor wrapping exactly
    one table, since walking further up finds whichever caption came first on the page.

    Args:
        node: The table.

    Returns:
        The caption, empty when the wrapper holds more than one table.
    """
    holder = node.parent
    for _ in range(4):
        if holder is None:
            break
        if len(holder.css("table")) == 1:
            found = holder.css_first("figcaption,caption")
            if found is not None:
                return " ".join(found.text().split())[:300]
        holder = holder.parent
    return ""


def read_tables(tree: LexborHTMLParser) -> list[Table]:
    """
    Every table in a paper, with whatever caption sits beside it

    Args:
        tree: The parsed html.

    Returns:
        One entry per table that held any row.
    """
    out: list[Table] = []
    for node in tree.css("table"):
        rows: list[list[str]] = []
        for line in node.css("tr"):
            cells = [read_cell(c) for c in line.css("td,th")]
            if any(cells):
                rows.append(cells)
        if not rows:
            continue
        out.append(Table(caption=read_caption(node), rows=rows))
    return out


def read_open(
    root: Path,
    arxiv_id: str,
    chars: int = SECTION_CHARS,
    fetch: bool = False,
) -> list[tuple[str, str]]:
    """
    The sections whose titles say the authors are discussing what they did not solve

    Args:
        root: The html store root.
        arxiv_id: The paper.
        chars: How much of each section to keep.
        fetch: Whether a paper the store never had may be fetched from arXiv.

    Returns:
        One title and body per matching section, empty when the html never landed.
    """
    found = read_paper(root, arxiv_id, fetch=fetch)
    if found is None:
        return []
    return [
        (name, body[:chars])
        for name, body in found.sections.items()
        if any(word in name.lower() for word in OPEN)
    ]


def read_paper(
    root: Path,
    arxiv_id: str,
    title: str = "",
    fetch: bool = False,
) -> FullText | None:
    """
    One paper's sections and tables, or None when the html never landed

    Args:
        root: The html store root.
        arxiv_id: The paper.
        title: Its title, carried through for the prompts.
        fetch: Whether a paper the store never had may be fetched from arXiv.

    Returns:
        The paper, or None.
    """
    path = html_file(root, arxiv_id, fetch)
    if path is None:
        return None
    try:
        tree = LexborHTMLParser(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return None
    sections: dict[str, str] = {}
    for node in tree.css("section"):
        head = node.css_first("h1,h2,h3")
        name = " ".join((head.text() if head else "").split())
        if not name:
            continue
        body = " ".join(node.text().split())
        if len(body) >= MIN_SECTION:
            sections.setdefault(name, body[:SECTION_CHARS])
    return FullText(arxiv_id=arxiv_id, title=title, sections=sections, tables=read_tables(tree))
