"""
A list of papers into what the field argues with, how it got there and what has answered it since

The list is expanded one citation hop first, since papers a reader kept rarely cite each other
The walk runs on the head of the list and the forward look on all of it, which pull opposite ways
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from pydantic import BaseModel, Field

from src.core.parse_graph_export import GraphExport
from src.core.schema import Edge, Lineage, Magnet, Paper
from src.miner import store
from src.miner.leyline import LeyLine
from src.miner.recipe import Recipe

LOG = logging.getLogger(__name__)

SENTENCE_FLOOR = 40
# the marker sits at the cited paper's slot, so one sentence differs per target until it is dropped
MARKS = re.compile(r"\d{4}[a-z]\b|\W|\d|CITE")
# without a cap the most argued with paper takes every slot and the section names one paper
PER_TARGET = 2


class Successor(BaseModel):
    """
    A paper that takes a position on the list, and which of it, in the words it used
    """

    paper: Paper
    targets: dict[str, str] = Field(default_factory=dict)
    sentences: list[str] = Field(default_factory=list)

    @property
    def reach(self) -> int:
        """
        How much of the list this paper positions itself against

        Returns:
            The count.
        """
        return len(self.targets)

    @property
    def pull(self) -> float:
        """
        How strongly a paper positions itself, held to the question by its own closeness to it

        Reach alone puts a paper that name checks four of the list above one that supersedes a
        single paper and is about exactly what was asked, so the two are multiplied.

        Returns:
            The key, higher first.
        """
        return self.reach * max(self.paper.cosine or 0.0, 0.0)


class Mined(BaseModel):
    """
    Everything one call found, with every paper it names carried alongside it
    """

    magnets: list[Magnet] = Field(default_factory=list)
    lineages: list[Lineage] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    disputes: list[Edge] = Field(default_factory=list)
    successors: list[Successor] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=list)
    papers: dict[str, Paper] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)


class Miner:
    """
    The whole package behind one call, holding the store, the graph and one mode's constants
    """

    def __init__(self, dsn: str, graph: GraphExport, recipe: Recipe) -> None:
        """
        Holds what every call needs, none of which changes between calls

        Args:
            dsn: libpq connection string.
            graph: The citation graph export.
            recipe: The miner block of the mode being run.
        """
        self.dsn = dsn
        self.graph = graph
        self.recipe = recipe

    def expand(self, arxiv_ids: list[str]) -> list[str]:
        """
        The papers a list cites, which is where the papers it argues with actually live

        Args:
            arxiv_ids: The list.

        Returns:
            The list and what it cites, in that order, each id once.
        """
        reached: set[int] = set()
        for arxiv_id in arxiv_ids:
            row = self.graph.index.get(arxiv_id)
            if row is None:
                continue
            reached.update(int(x) for x in self.graph.get_cited_papers(row))
        return list(dict.fromkeys(arxiv_ids + [self.graph.ids[i].decode() for i in reached]))

    def mine(self, papers: list[Paper], vector: list[float], asked: date) -> Mined:
        """
        Everything this package knows about one list of papers

        Args:
            papers: The papers to mine, best first.
            vector: The question embedding, which holds every part of the result to what was asked.
            asked: The date the run is capped at.

        Returns:
            What was found.
        """
        if not papers:
            return Mined()
        arxiv_ids = [p.arxiv_id for p in papers]
        union = self.expand(arxiv_ids[: self.recipe.walk_prefix])
        held = {p.arxiv_id: p for p in store.read_papers(self.dsn, vector, union)}
        held |= {p.arxiv_id: p for p in papers}
        edges = store.read_edges(self.dsn, union)

        scores = {a: max(p.cosine or 0.0, 0.0) for a, p in held.items()}
        order = {a: float(p.date.toordinal()) for a, p in held.items()}
        line = LeyLine(edges, self.recipe.settings, scores, order, focus=scores)
        magnets = line.magnets()
        lineages = line.lineages()
        connectors = line.connectors(set(arxiv_ids), self.recipe.connectors)
        disputes = self.disputes(edges, {m.node: m.weight for m in magnets})
        ahead = self.successors(arxiv_ids, vector, asked)

        named = {n for line_ in lineages for n in line_.nodes}
        named |= {m.node for m in magnets} | set(connectors)
        for one in ahead:
            held[one.paper.arxiv_id] = one.paper
        LOG.info(
            "mined %d papers: union %d, edges %d, magnets %d, lineages %d, successors %d",
            len(papers),
            len(union),
            len(edges),
            len(magnets),
            len(lineages),
            len(ahead),
        )
        return Mined(
            magnets=magnets,
            lineages=lineages,
            edges=edges,
            disputes=disputes,
            successors=ahead,
            connectors=connectors,
            papers=held,
            counts={
                "papers": len(papers),
                "union": len(union),
                "edges": len(edges),
                "magnets": len(magnets),
                "lineages": len(lineages),
                "successors": len(ahead),
            },
        )

    def disputes(
        self,
        edges: list[Edge],
        weight: dict[str, float],
        intents: tuple[str, ...] = (),
        sources: set[str] | None = None,
    ) -> list[Edge]:
        """
        One sentence per citing pair that took a position, the most argued with paper first

        Read off the edges rather than off the paths, since one sentence sits on several paths.

        Args:
            edges: The labeled citations.
            weight: Magnet weight per paper, which orders the result.
            intents: Which labels count, the recipe's argued with labels when empty.
            sources: The only papers whose sentences count, every paper when None.

        Returns:
            The sentences.
        """
        counted = intents or self.recipe.settings.argues
        seen: set[tuple[str, str]] = set()
        # one sentence citing six papers would otherwise be quoted six times
        said: set[tuple[str, str]] = set()
        held: dict[str, int] = {}
        out: list[Edge] = []
        for edge in sorted(edges, key=lambda e: -weight.get(e.target, 0.0)):
            if edge.intent not in counted:
                continue
            if sources is not None and edge.source not in sources:
                continue
            if len(edge.sentence) < SENTENCE_FLOOR or (edge.source, edge.target) in seen:
                continue
            words = MARKS.sub("", edge.sentence)
            if held.get(edge.target, 0) >= PER_TARGET or (edge.source, words) in said:
                continue
            seen.add((edge.source, edge.target))
            said.add((edge.source, words))
            held[edge.target] = held.get(edge.target, 0) + 1
            out.append(edge)
        return out

    def successors(self, arxiv_ids: list[str], vector: list[float], asked: date) -> list[Successor]:
        """
        Papers from the recent window that extend, dispute or benchmark against the list

        Args:
            arxiv_ids: The list being cited.
            vector: The question embedding.
            asked: The date the run is capped at.

        Returns:
            The papers, the ones reaching most of the list first.
        """
        rows = store.read_successors(
            self.dsn,
            vector,
            arxiv_ids,
            asked - timedelta(days=self.recipe.successor_days),
            asked,
            self.recipe.successor_intents,
            self.recipe.successor_floor,
        )
        held = set(arxiv_ids)
        out = [
            Successor(paper=paper, targets=targets, sentences=sentences)
            for key, (paper, targets, sentences) in rows.items()
            if key not in held
        ]
        return sorted(out, key=lambda s: -s.pull)
