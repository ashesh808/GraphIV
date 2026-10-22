"""
Telling one person's papers from a namesake's, and grouping and picking their topics

Every input is hand built, so nothing here reaches the store
"""

from __future__ import annotations

import pytest

from src.retrieve.people import (
    THRESHOLD,
    UNPLACED,
    Person,
    as_people,
    authors,
    best_topic,
    group,
    propagate,
)

# k is known, a shares two coauthors with it, b shares two with a, z belongs to a namesake
COAUTHORS = {
    "k": {"Ada", "Bo"},
    "a": {"Ada", "Bo", "Cy"},
    "b": {"Cy", "Dee", "Ada"},
    "z": {"Xu"},
}
REFERENCES = {"k": {"r1"}, "a": {"r1"}, "b": set(), "z": {"r9"}}


def test_a_paper_sharing_two_coauthors_with_a_known_one_is_kept():
    prob = propagate(COAUTHORS, REFERENCES, {"k"})
    assert prob["a"] >= THRESHOLD


def test_the_propagation_reaches_past_the_first_hop():
    prob = propagate(COAUTHORS, REFERENCES, {"k"})
    assert prob["b"] >= THRESHOLD


def test_a_paper_sharing_nothing_stays_out():
    prob = propagate(COAUTHORS, REFERENCES, {"k"})
    assert prob["z"] < THRESHOLD


def test_one_shared_coauthor_alone_is_not_enough():
    prob = propagate({"k": {"Ada"}, "q": {"Ada"}}, {}, {"k"})
    assert prob["q"] < THRESHOLD


def test_known_papers_stay_certain():
    assert propagate(COAUTHORS, REFERENCES, {"k"})["k"] == 1.0


def test_a_person_needs_a_known_paper():
    with pytest.raises(ValueError):
        _ = as_people([{"name": "Ada Lovelace"}])


def test_a_single_known_id_may_be_a_string():
    assert as_people([{"name": " Ada  Lovelace ", "known": "1234.5678"}]) == [
        Person("Ada Lovelace", ("1234.5678",))
    ]


def test_authors_split_on_commas_and_and():
    assert authors("Ada Lovelace, Bo Li and Cy  Young") == ["Ada Lovelace", "Bo Li", "Cy Young"]


def test_unplaced_papers_get_a_group_of_their_own():
    got = group(["a", "b", "c"], {"a": (1, 2), "b": (1, 2)})
    assert got == {(1, 2): ["a", "b"], UNPLACED: ["c"]}


def test_the_topic_closest_on_average_wins():
    groups = {(0, 1): ["a", "b"], (0, 2): ["c"]}
    assert best_topic(groups, {"a": 0.9, "b": 0.1, "c": 0.6}) == (0, 2)


def test_no_cosines_pick_no_topic():
    assert best_topic({(0, 1): ["a"]}, {}) is None
