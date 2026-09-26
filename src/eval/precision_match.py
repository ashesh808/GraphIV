"""
Given what a query returned, find how much of it is not about the topic at all

A paper counts as related when it shares the review's leaf or a reviewer of that leaf cites it
Both signals sit in the graph export, so the judge costs no gpu and no llm call
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from src.core.parse_graph_export import GraphExport
from src.eval.cases import Sample
from src.eval.match import Match, Score

LOG = logging.getLogger(__name__)


class PrecisionMatch(Match):
    """
    One review per sample, scored on the share of its answer that is on topic
    """

    name: str = "PrecisionMatch"
    headline: str = "1000"

    def __init__(
        self,
        writer: object,
        budgets: list[int],
        graph: GraphExport,
        *,
        survey_threshold: float = 0.95,
    ) -> None:
        """
        Holds the graph, since both halves of the judge are graph lookups

        Args:
            writer: Writes the query, or None to fall back to the stripped titles.
            budgets: The rank bands the report breaks the score down by.
            graph: The citation graph export.
            survey_threshold: The floor a paper must clear to count as a reviewer of the leaf.
        """
        super().__init__(writer, budgets)  # pyright: ignore[reportArgumentType]
        self.graph = graph
        self.survey_threshold = survey_threshold

    def get_leaf_union(self, leaf: list[int], drop: list[str]) -> NDArray[np.bool_]:
        """
        Every paper a reviewer of this leaf cites, with the sample's own reviews held out

        Args:
            leaf: The three tree ids.
            drop: The sample's own reviews.

        Returns:
            A mask over the corpus.
        """
        level = self.graph.level
        here = np.flatnonzero(
            (level[:, 0] == leaf[0])
            & (level[:, 1] == leaf[1])
            & (level[:, 2] == leaf[2])
            & (self.graph.survey >= self.survey_threshold)
        )
        blocked = {self.graph.index[a] for a in drop if a in self.graph.index}
        out = np.zeros(self.graph.n_papers, np.bool_)
        for row in here:
            if int(row) not in blocked:
                out[np.asarray(self.graph.get_cited_papers(int(row)))] = True
        return out

    def compute_score(self, sample: Sample, ranked: list[str], seconds: float) -> Score:
        """
        The share of the answer that shares the leaf or that a reviewer of it cites

        `recall` carries the share per rank band rather than a recall, since this benchmark has no
        answer key and a lower number is the better one.

        Args:
            sample: The mined sample.
            ranked: Every candidate the pipeline considered, best first.
            seconds: What the query cost.

        Returns:
            The filled score, whose headline is the share over the whole returned list.
        """
        union = self.get_leaf_union(sample.leaf, sample.anchors)
        rows = np.array([self.graph.index[a] for a in ranked if a in self.graph.index], np.int32)
        level = self.graph.level[rows]
        same_leaf = (
            (level[:, 0] == sample.leaf[0])
            & (level[:, 1] == sample.leaf[1])
            & (level[:, 2] == sample.leaf[2])
        )
        related = same_leaf | union[rows]
        top = max(self.budgets)
        return Score(
            sample_id=sample.sample_id,
            anchors=sample.anchors,
            anchor_titles=sample.titles,
            query=self.build_query(sample),
            cutoff=sample.cutoff,
            n_key=0,
            n_pool=len(ranked),
            ceiling=float(related[:top].mean()) if len(related) else 0.0,
            seconds=seconds,
            hits={str(k): int(related[:k].sum()) for k in self.budgets},
            recall={
                str(k): float(related[:k].mean()) if len(related) else 0.0 for k in self.budgets
            },
            key=[],
            found=[a for a, ok in zip(ranked, related.tolist(), strict=False) if ok][:top],
            extra={"same_leaf": float(same_leaf[:top].mean()) if len(related) else 0.0},
        )
