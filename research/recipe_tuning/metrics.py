"""
What every benchmark shares: one published case, the score it returns and the row it writes

A metric differs only in its name and the cutoff its headline recall is read at
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import pyarrow.parquet as pq

FOLDERS = {
    "SurveyMatch": "surveymatch",
    "FrontierMatch": "frontiermatch",
    "ConsensusMatch": "consensusmatch",
    "PrecisionMatch": "surveymatch",
}


@dataclass(frozen=True)
class Sample:
    """
    One published case, self contained so a run reads nothing else
    """

    sample_id: str
    anchors: list[str]
    titles: list[str]
    leaf: list[int]
    cutoff: str
    key: list[str]
    query: str
    extra: dict[str, float] = field(default_factory=dict)


def read_cases(root: Path, metric: str, split: str, limit: int = 0) -> list[Sample]:
    """
    One split of a published benchmark as the samples a run scores

    Args:
        root: The benchmark release, graphiv-benchmarks-<cutoff>.
        metric: SurveyMatch, FrontierMatch, ConsensusMatch or PrecisionMatch.
        split: train, val or test.
        limit: The most cases to read, every case when zero.

    Returns:
        The samples.
    """
    rows = pq.read_table(root / FOLDERS[metric] / f"{split}.parquet").to_pylist()
    rows = rows[:limit] if limit else rows
    return [
        Sample(
            sample_id=str(r["case_id"]),
            anchors=list(r["anchors"]),
            titles=list(r["anchor_titles"]),
            leaf=[int(r["topic_l0"]), int(r["topic_l1"]), int(r["topic_l2"])],
            cutoff=r["date_max"].isoformat(),
            key=list(r["citations"]),
            query=str(r["query_text"]),
            extra={k: float(r[k]) for k in ("gap_days", "cosine") if r[k] is not None},
        )
        for r in rows
    ]


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


class Match:
    """
    The shared half of a benchmark, which every metric subclasses
    """

    name: str = "Match"
    headline: str = "1000"

    def __init__(self, budgets: list[int]) -> None:
        """
        Holds the budgets a score reports

        Args:
            budgets: The cutoffs a score reports recall at.
        """
        self.budgets = budgets

    def compute_score(self, sample: Sample, ranked: list[str], seconds: float) -> Score:
        """
        Recall of the sample's key at every budget, and how much of it was reachable at all

        `ranked` is the whole pool in score order rather than the top of it, so the ceiling and
        the recall come out of one call and a ranking failure is told apart from a reach failure.

        Args:
            sample: The published sample.
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
            query=sample.query,
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


class SurveyMatch(Match):
    """
    Given one review, find the papers it cited
    """

    name: str = "SurveyMatch"
    headline: str = "1000"


class FrontierMatch(Match):
    """
    Given a topic as one review left it, find what the next review on it added
    """

    name: str = "FrontierMatch"
    headline: str = "1000"


class ConsensusMatch(Match):
    """
    Given a topic, find the papers every review of it cites

    A key of eight saturates a thousand slots, so the headline budget is a hundred
    """

    name: str = "ConsensusMatch"
    headline: str = "100"
