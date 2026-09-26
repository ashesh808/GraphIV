"""
Where a field's current era starts, on histograms shaped like a fast field and a flat one
"""

from __future__ import annotations

from datetime import date

from src.miner.era import MAX_SPAN, detect, per_year

ASKED = date(2026, 9, 26)


def years(counts: dict[int, int]) -> list[date]:
    return [date(year, 6, 1) for year, many in counts.items() for _ in range(many)]


def test_a_fast_field_cuts_at_the_surge():
    counts = {2020: 100, 2021: 150, 2022: 250, 2023: 1100, 2024: 2600, 2025: 4000, 2026: 4200}
    assert detect(years(counts), ASKED).year == 2024


def test_a_flat_field_runs_back_to_the_clamp():
    counts = {y: 400 for y in range(2012, 2027)}
    assert detect(years(counts), ASKED).year == ASKED.year - MAX_SPAN


def test_the_asking_year_never_ends_the_walk_on_its_own():
    counts = {2023: 500, 2024: 500, 2025: 500, 2026: 3}
    assert detect(years(counts), ASKED).year <= 2023


def test_a_dormant_field_reports_its_last_active_year():
    counts = {2001: 40, 2002: 60}
    assert detect(years(counts), ASKED).year == 2002


def test_nothing_retrieved_is_not_an_error():
    assert detect([], ASKED).year == ASKED.year - 1


def test_citations_per_year_judges_a_new_paper_on_its_opportunity():
    old = per_year(100, date(2016, 1, 1), ASKED)
    new = per_year(20, date(2025, 1, 1), ASKED)
    assert new > old
