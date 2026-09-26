"""
The ranking that puts a past report in front of a new question

Vectors are hand built, so nothing here embeds anything or reaches an endpoint
"""

from __future__ import annotations

from src.mcp.find_runs import cosine, rank

RUNS = [
    {"slug": "old-tabular", "question": "foundation models for tabular data"},
    {"slug": "old-graphs", "question": "temporal knowledge graphs"},
    {"slug": "old-none", "question": ""},
]
VECTORS = {"old-tabular": [1.0, 0.0], "old-graphs": [0.0, 1.0]}


def test_two_identical_vectors_are_one():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_vectors_of_different_lengths_score_nothing():
    assert cosine([1.0], [1.0, 0.0]) == 0.0


def test_an_empty_vector_scores_nothing():
    assert cosine([], []) == 0.0


def test_the_closest_run_comes_first():
    got = rank([1.0, 0.0], RUNS, VECTORS)
    assert [r["slug"] for r in got] == ["old-tabular", "old-graphs", "old-none"]


def test_a_run_with_no_vector_sorts_last():
    got = rank([0.0, 1.0], RUNS, VECTORS)
    assert got[0]["slug"] == "old-graphs"
    assert got[-1]["slug"] == "old-none"


def test_the_ranking_carries_the_closeness_it_scored():
    got = rank([1.0, 0.0], RUNS, VECTORS)
    assert got[0]["closeness"] == 1.0
    assert got[-1]["closeness"] == 0.0


def test_the_rows_given_are_not_changed():
    _ = rank([1.0, 0.0], RUNS, VECTORS)
    assert "closeness" not in RUNS[0]
