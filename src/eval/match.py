"""
What every benchmark shares: the query it asks, the score it returns and the row it writes

A metric differs only in how it turns a sample into a question and what counts as a right answer
The pipeline arrives as a callable, so nothing here imports the retriever
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Protocol

from src.eval.cases import Sample

LOG = logging.getLogger(__name__)

Pipeline = Callable[[Sample, str], list[str]]

_QUALIFIER = r"(comprehensive |systematic |critical |brief |short |recent |modern )*"
_WORD = r"(survey|review|overview|tutorial)"
_PREP = r"( of| on| for| about)?"
_LEAD = re.compile(rf"^(a |an |the )?{_QUALIFIER}{_WORD}{_PREP}\b[:,]?\s*", re.IGNORECASE)
_TAIL = re.compile(
    rf"[,:]?\s*(a |an )?{_QUALIFIER}{_WORD}{_PREP}( the)?( recent| current| existing)?"
    r"( literature| research| work| works| studies| advances| developments| progress)?$",
    re.IGNORECASE,
)


def strip_boilerplate(title: str) -> str:
    """
    A review title with the review words removed, which is the fallback query

    Args:
        title: The raw title.

    Returns:
        The topic segments, or the title when nothing survives.
    """
    segments = re.split(r"\s*:\s*", re.sub(r"\s+", " ", title).strip())
    stripped = (_TAIL.sub("", _LEAD.sub("", seg)).strip(" ,-") for seg in segments)
    kept = [seg for seg in stripped if len(seg) >= 12]
    return ": ".join(kept) if kept else title


@dataclass
class Score:
    """
    One sample under one recipe, carrying enough to redo any statistic without the store
    """

    sample_id: str
    anchors: list[str]
    anchor_titles: list[str]
    query: str
    cutoff: str
    n_key: int
    n_pool: int
    ceiling: float
    seconds: float
    hits: dict[str, int] = field(default_factory=dict)
    recall: dict[str, float] = field(default_factory=dict)
    key: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)
    extra: dict[str, float] = field(default_factory=dict)

    def as_row(self) -> dict[str, object]:
        """
        The score as one jsonl line

        Returns:
            A plain dict.
        """
        return asdict(self)


class QueryWriter(Protocol):
    """
    Turns a sample's reviews into the one question a reader would have asked
    """

    def write(self, titles: list[str], abstracts: list[str]) -> str:
        """
        Returns the question the reviews would have been written to answer

        Args:
            titles: The review titles.
            abstracts: Their abstracts.

        Returns:
            One question.
        """
        ...


class Match:
    """
    The shared half of a benchmark, which every metric subclasses
    """

    name: str = "Match"
    headline: str = "1000"

    def __init__(self, writer: QueryWriter | None, budgets: list[int]) -> None:
        """
        Holds how a question is written and which budgets a score reports

        Args:
            writer: Writes the query, or None to fall back to the stripped titles.
            budgets: The cut-offs a score reports recall at.
        """
        self.writer = writer
        self.budgets = budgets

    def build_query(self, sample: Sample) -> str:
        """
        The question this sample asks, frozen onto the sample the first time it is written

        Args:
            sample: The mined sample.

        Returns:
            The question.
        """
        if sample.query:
            return sample.query
        if self.writer is None:
            return "; ".join(strip_boilerplate(t) for t in sample.titles)
        return self.writer.write(sample.titles, sample.abstracts)

    def compute_score(self, sample: Sample, ranked: list[str], seconds: float) -> Score:
        """
        Recall of the sample's key at every budget, and how much of it was reachable at all

        `ranked` is the whole pool in score order rather than the top of it, so the ceiling and
        the recall come out of one call and a ranking failure is told apart from a reach failure.

        Args:
            sample: The mined sample.
            ranked: Every candidate the pipeline considered, best first.
            seconds: What the query cost.

        Returns:
            The filled score.
        """
        key = set(sample.key)
        found = [a for a in ranked if a in key]
        hits = {str(k): len([a for a in ranked[:k] if a in key]) for k in self.budgets}
        return Score(
            sample_id=sample.sample_id,
            anchors=sample.anchors,
            anchor_titles=sample.titles,
            query=self.build_query(sample),
            cutoff=sample.cutoff,
            n_key=len(key),
            n_pool=len(ranked),
            ceiling=len(found) / len(key) if key else 0.0,
            seconds=seconds,
            hits=hits,
            recall={k: v / len(key) if key else 0.0 for k, v in hits.items()},
            key=sample.key,
            found=found,
            extra=dict(sample.extra),
        )
