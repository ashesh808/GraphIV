"""
Data contracts that flow between retrieval, generation and the dashboard

They live below the store because the store constructs them straight from SQL rows.
"""

from __future__ import annotations

from dataclasses import dataclass

"""
Intent labels strongest-signal first, collapsing parallel edges down to one

extends and uses mean builds-on, compares and critiques and motivates frame a limitation
Background is the weakest signal and sorts last
"""
INTENT_PRIORITY: list[str] = [
    "extends",
    "uses",
    "compares",
    "critiques",
    "motivates",
    "background",
]
_INTENT_RANK: dict[str, int] = {name: i for i, name in enumerate(INTENT_PRIORITY)}
TENSION_INTENTS: frozenset[str] = frozenset({"compares", "critiques", "motivates"})


@dataclass
class PoolNode:
    """
    One retrieved paper and its similarity to the query
    """

    arxiv_id: str
    title: str
    year: int | None
    category: str | None
    # cosine sim to the query
    score: float


@dataclass
class Edge:
    """
    One collapsed citation edge carrying its strongest-signal intent
    """

    # citing (newer) cites dst (older)
    src: str
    dst: str
    intent: str | None


@dataclass
class Landmark:
    """
    A pool paper promoted to the report cohort, with its graph and reader verdict
    """

    arxiv_id: str
    title: str
    year: int | None
    category: str | None
    score: float
    # distinct pool papers citing this one
    in_degree: int
    # filled by assign_eras
    era: int = -1
    # reader grade 6-class label, when graded
    role: str | None = None
    # reader grade -2..2, when graded
    relevance: int | None = None


@dataclass
class Era:
    """
    One contiguous slice of the cohort's publication timeline
    """

    index: int
    label: str
    year_lo: int
    year_hi: int


def intent_rank(intent: str | None) -> int:
    """
    Position of an intent in INTENT_PRIORITY; unknown and missing sort last

    Args:
        intent: intent label from the citation classifier.

    Returns:
        Index into INTENT_PRIORITY, or len(INTENT_PRIORITY) for anything absent.
    """
    return _INTENT_RANK.get(intent or "", len(INTENT_PRIORITY))
