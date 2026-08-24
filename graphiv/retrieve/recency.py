"""
Locate a field's active frontier from its own year distribution, anchored to today

A fixed cutoff buries recent work in a fast field and admits noise in a slow one
The age-normalized score lets a fast-rising recent paper compete with an old citation hub
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# only look this far back when locating the recent surge / peak
_WINDOW = 7
# a year is part of the active band if it has >= this share of the recent peak volume
_ACTIVE_SHARE = 0.30
# never stretch the detected frontier older than this many years before now
_MAX_SPAN = 6


@dataclass
class FrontierSpec:
    """
    Where a topic's frontier sits, and how many slots it reserves
    """

    frontier_year: int  # papers with year >= this are "frontier" for this topic
    recent_floor: int  # landmark slots reserved for frontier papers
    now_year: int


def detect_frontier(
    years: list[int],
    now_year: int,
    now_month: int,
    m: int,
    recency: float,
) -> FrontierSpec:
    """
    Detect the topic's active-frontier cutoff from its year histogram

        Walks back from `now_year` while each year stays "active" (>= `_ACTIVE_SHARE` of the
        recent peak), giving the current year a pass when it is only part-elapsed. The reserved
        `recent_floor` scales with the `recency` knob (0..1) and the landmark budget `m`.
    """
    _ = now_month  # reserved: part-year scaling; the current-year pass below uses it implicitly
    floor = max(1, round(recency * m))
    yrs = [y for y in years if y <= now_year]
    if not yrs:
        return FrontierSpec(now_year - 1, floor, now_year)

    counts: dict[int, int] = {}
    for y in yrs:
        counts[y] = counts.get(y, 0) + 1
    latest = max(counts)

    window_lo = now_year - _WINDOW
    recent = {y: c for y, c in counts.items() if y >= window_lo}
    if not recent:
        # dormant topic: its frontier is simply its most recent year of activity
        return FrontierSpec(latest, floor, now_year)

    peak = max(recent.values())
    thresh = max(1.0, _ACTIVE_SHARE * peak)
    frontier_year = latest
    y = now_year
    while y >= window_lo:
        c = counts.get(y, 0)
        if c >= thresh:
            frontier_year = y
            y -= 1
        elif y == now_year:
            # the current year is only part-elapsed; don't let a thin count end the band
            y -= 1
        else:
            break

    frontier_year = max(min(frontier_year, latest), now_year - _MAX_SPAN)
    return FrontierSpec(frontier_year, floor, now_year)


class _HasYearScore(Protocol):
    year: int | None
    score: float


def frontier_select[T: _HasYearScore](items: list[T], recent_year: int, floor: int) -> list[T]:
    """
    Pick up to `floor` frontier items, NEWEST-YEAR-FIRST round-robin (similarity-ranked

        within each year). Guarantees the latest cohorts (e.g. 2025 AND 2026) each get slots
        instead of being starved by slightly-older, higher-similarity papers, the exact failure
        that buried new work when the reservation was ranked by similarity alone.
    """
    if floor <= 0:
        return []
    by_year: dict[int, list[T]] = {}
    for it in items:
        if it.year is not None and it.year >= recent_year:
            by_year.setdefault(it.year, []).append(it)
    for y in by_year:
        by_year[y].sort(key=lambda it: it.score, reverse=True)
    years_desc = sorted(by_year, reverse=True)
    chosen: list[T] = []
    cursor = {y: 0 for y in years_desc}
    while len(chosen) < floor:
        progressed = False
        for y in years_desc:  # newest year first each round
            i = cursor[y]
            if i < len(by_year[y]):
                chosen.append(by_year[y][i])
                cursor[y] = i + 1
                progressed = True
                if len(chosen) >= floor:
                    break
        if not progressed:
            break
    return chosen


def age_norm_score(in_degree: int, year: int | None, now_year: int) -> float:
    """
    Citations-per-year: in-degree normalized by paper age so a recent paper with few

        but fast citations competes with an old hub. Undated papers fall back to raw in-degree.
    """
    if year is None:
        return float(in_degree)
    age = max(0.5, float(now_year - year))
    return in_degree / age
