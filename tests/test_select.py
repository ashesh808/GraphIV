"""
The selector registry: scores, the shared assembler and the two structural flags

Every case runs on the hand-built fixture pool, so nothing here touches a database
"""

from __future__ import annotations

import pytest

from graphiv.core.models import PoolNode
from graphiv.retrieve.api import Selection
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import FrontierSpec
from graphiv.retrieve.select import (
    SELECTORS,
    NamedSelector,
    Recipe,
    assemble,
    in_degree,
    percentile,
    relevance,
    score_citations_per_year,
    score_cosine,
    score_indegree,
    score_joint,
)


def test_in_degree_counts_only_incoming(selection: Selection) -> None:
    assert in_degree(selection) == {"old.1": 3, "mid.1": 1}


def test_percentile_is_one_at_the_top_and_zero_at_the_bottom() -> None:
    p = percentile({"a": 3.0, "b": 2.0, "c": 1.0})
    assert p["a"] == pytest.approx(1.0)
    assert p["c"] == pytest.approx(0.0)


def test_relevance_is_neutral_for_an_ungraded_paper(selection: Selection) -> None:
    assert relevance(selection)["old.2"] == pytest.approx(0.5)
    assert relevance(selection)["new.1"] == pytest.approx(1.0)


def test_indegree_ranks_the_hub_first(selection: Selection) -> None:
    s = score_indegree(selection)
    assert max(s, key=lambda a: s[a]) == "old.1"


def test_citations_per_year_beats_raw_indegree_on_recency(selection: Selection) -> None:
    """
    mid.1 has one citation in six years and old.1 has three in eleven, so age matters
    """
    raw = score_indegree(selection)
    normed = score_citations_per_year(selection)
    assert raw["old.1"] > raw["mid.1"]
    assert normed["old.1"] / normed["mid.1"] < raw["old.1"] / raw["mid.1"]


def test_cosine_score_is_the_pool_score(selection: Selection) -> None:
    assert score_cosine(selection)["old.1"] == pytest.approx(0.61)


def test_joint_puts_a_graded_frontier_paper_above_an_ungraded_one(selection: Selection) -> None:
    s = score_joint(selection)
    assert s["new.1"] > s["old.2"]


def test_every_registered_selector_returns_the_budget(selection: Selection) -> None:
    for name in SELECTORS:
        got = NamedSelector(name).select(selection)
        assert len(got) == selection.budget, name
        assert len({lm.arxiv_id for lm in got}) == len(got), name


def test_unknown_selector_raises() -> None:
    with pytest.raises(KeyError):
        _ = NamedSelector("does-not-exist")


def test_reservation_guarantees_a_frontier_paper(selection: Selection) -> None:
    """
    Unfused cosine takes the four oldest papers, so the reservation is what changes it
    """
    plain = {lm.arxiv_id for lm in assemble(selection, Recipe(score_cosine, fuse=False))}
    reserved = {
        lm.arxiv_id for lm in assemble(selection, Recipe(score_cosine, reserve=True, fuse=False))
    }
    assert {"new.1", "new.2"}.isdisjoint(plain)
    assert {"new.1", "new.2"} <= reserved


def test_fusion_drops_a_rejected_paper_from_the_ranking(selection: Selection) -> None:
    """
    A -2 paper leaves the cohort but stays in the pool as a graph connector
    """
    rejected = dict(selection.grades) | {"old.1": Grade("unrelated", -2, "off topic")}
    sel = Selection(selection.pool, selection.edges, 4, selection.fr, rejected)
    got = {lm.arxiv_id for lm in assemble(sel, Recipe(score_indegree))}
    assert "old.1" not in got


def test_fuse_false_keeps_a_rejected_paper(selection: Selection) -> None:
    rejected = dict(selection.grades) | {"old.1": Grade("unrelated", -2, "off topic")}
    sel = Selection(selection.pool, selection.edges, 4, selection.fr, rejected)
    got = {lm.arxiv_id for lm in assemble(sel, Recipe(score_indegree, fuse=False))}
    assert "old.1" in got


def test_landmarks_carry_true_similarity_not_the_ranking_score(selection: Selection) -> None:
    for lm in assemble(selection, Recipe(score_indegree)):
        assert lm.score == pytest.approx(selection.pool[lm.arxiv_id].score)


def test_landmarks_carry_the_reader_verdict(selection: Selection) -> None:
    got = {lm.arxiv_id: lm for lm in assemble(selection, Recipe(score_joint))}
    assert got["new.1"].role == "frontier"
    assert got["new.1"].relevance == 2


def test_budget_larger_than_the_pool_returns_the_pool(selection: Selection) -> None:
    big = Selection(selection.pool, selection.edges, 99, selection.fr, selection.grades)
    assert len(assemble(big, Recipe(score_cosine))) == len(selection.pool)


def test_empty_pool_returns_nothing() -> None:
    empty = Selection({}, [], 4, FrontierSpec(2025, 2, 2026), {})
    assert assemble(empty, Recipe(score_cosine)) == []


def test_a_pool_with_no_edges_still_selects(selection: Selection) -> None:
    flat = Selection(selection.pool, [], 4, selection.fr, selection.grades)
    assert len(assemble(flat, Recipe(score_citations_per_year))) == 4


def test_selection_is_deterministic(selection: Selection) -> None:
    first = [lm.arxiv_id for lm in NamedSelector("joint").select(selection)]
    second = [lm.arxiv_id for lm in NamedSelector("joint").select(selection)]
    assert first == second


def test_ties_break_by_id_not_by_dict_order() -> None:
    """
    Two papers with identical scores must come back in a stable order
    """
    nodes = {a: PoolNode(a, a, 2020, "cs", 0.5) for a in ("b", "a", "c")}
    sel = Selection(nodes, [], 2, FrontierSpec(2025, 0, 2026), {})
    assert [lm.arxiv_id for lm in assemble(sel, Recipe(score_cosine))] == ["a", "b"]


def test_grades_outside_the_pool_are_ignored(selection: Selection) -> None:
    stray = dict(selection.grades) | {"not.in.pool": Grade("core", 2, "stray")}
    sel = Selection(selection.pool, selection.edges, 4, selection.fr, stray)
    got = {lm.arxiv_id for lm in NamedSelector("joint").select(sel)}
    assert "not.in.pool" not in got
