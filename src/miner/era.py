"""
Where a field's current era starts, read off the dates of the papers retrieved for it

A fixed cutoff buries recent work in a fast field and admits a decade of it in a slow one
Citations per year is the other half, so a fast-rising new paper competes with an old hub
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Protocol


class Dated(Protocol):
    """
    Anything carrying the date a cohort is read off
    """

    date: date


# only look this far back when locating the recent peak
WINDOW = 7
# a year joins the era when it holds at least this share of the peak year's volume
ACTIVE_SHARE = 0.30
# never stretch the era further back than this
MAX_SPAN = 6


@dataclass(frozen=True)
class Era:
    """
    The first year that counts as current, and the histogram it was read from
    """

    year: int
    counts: dict[int, int]

    def holds(self, when: date) -> bool:
        """
        Whether one date falls inside the era

        Args:
            when: The paper's date.

        Returns:
            True when the paper is current.
        """
        return when.year >= self.year


def detect(dates: list[date], asked: date) -> Era:
    """
    Walks back from the asking year while each year still carries the field's volume

    The asking year is given a pass because it is only part elapsed, and the walk is clamped so a
    field flat for a decade still reports an era rather than its whole history.

    Args:
        dates: Every retrieved paper's date.
        asked: The date the run is capped at.

    Returns:
        The era.
    """
    counts = Counter(d.year for d in dates if d.year <= asked.year)
    if not counts:
        return Era(asked.year - 1, {})
    latest = max(counts)
    floor = asked.year - WINDOW
    recent = {y: c for y, c in counts.items() if y >= floor}
    if not recent:
        return Era(latest, dict(counts))

    live = max(1.0, ACTIVE_SHARE * max(recent.values()))
    year = latest
    walking = asked.year
    while walking >= floor:
        if counts.get(walking, 0) >= live:
            year = walking
        elif walking != asked.year:
            break
        walking -= 1
    return Era(max(min(year, latest), asked.year - MAX_SPAN), dict(counts))


def per_year(citations: int, when: date, asked: date) -> float:
    """
    Citations normalized by how long the paper has had to collect them

    Args:
        citations: How many papers cite it.
        when: The paper's date.
        asked: The date the run is capped at.

    Returns:
        The rate, which is the raw count for a paper younger than half a year.
    """
    age = max(0.5, float(asked.year - when.year))
    return citations / age


def cohorts[T: Dated](papers: list[T], limit: int) -> list[T]:
    """
    Fills a budget newest year first, taking the best of each year in turn

    Ranking the budget by score alone hands every slot to the oldest cohort, since a paper needs
    years to collect the citations the score is mostly made of.

    Args:
        papers: The candidates, best first by whatever the caller ranked them on.
        limit: How many to return.

    Returns:
        At most `limit` papers, with every year in the era represented.
    """
    if limit <= 0:
        return []
    by_year: dict[int, list[T]] = {}
    for paper in papers:
        by_year.setdefault(paper.date.year, []).append(paper)
    order = sorted(by_year, reverse=True)
    out: list[T] = []
    spot = {year: 0 for year in order}
    while len(out) < limit:
        moved = False
        for year in order:
            held = spot[year]
            if held < len(by_year[year]):
                out.append(by_year[year][held])
                spot[year] = held + 1
                moved = True
                if len(out) >= limit:
                    break
        if not moved:
            break
    return out
