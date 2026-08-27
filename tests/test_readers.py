"""
The reader stage, covering every implementation that needs no endpoint

LlmReader is exercised only through its registry entry, since calling it needs a router
"""

from __future__ import annotations

import pytest

from graphiv.retrieve.api import Pool, Query
from graphiv.retrieve.readers import READERS, ConstantReader, GoldReader, NullReader


def test_null_reader_grades_nothing(query: Query, pool: Pool) -> None:
    assert NullReader().grade(query, pool) == {}


def test_constant_reader_grades_every_candidate_the_same(query: Query, pool: Pool) -> None:
    got = ConstantReader().grade(query, pool)
    assert set(got) <= set(pool.nodes)
    assert {g.relevance for g in got.values()} == {1}


def test_constant_reader_relevance_is_configurable(query: Query, pool: Pool) -> None:
    got = ConstantReader(relevance=2, role="frontier").grade(query, pool)
    assert {(g.role, g.relevance) for g in got.values()} == {("frontier", 2)}


def test_gold_reader_splits_the_pool_by_the_answer_key(query: Query, pool: Pool) -> None:
    got = GoldReader({query.text: {"old.1", "new.1"}}).grade(query, pool)
    assert got["old.1"].relevance == 2
    assert got["new.1"].relevance == 2
    assert got["mid.1"].relevance == -2


def test_gold_reader_with_no_key_for_this_question_rejects_everything(
    query: Query, pool: Pool
) -> None:
    got = GoldReader({}).grade(query, pool)
    assert {g.relevance for g in got.values()} == {-2}


def test_a_reader_never_invents_a_paper(query: Query, pool: Pool) -> None:
    for reader in (NullReader(), ConstantReader(), GoldReader({})):
        assert set(reader.grade(query, pool)) <= set(pool.nodes)


def test_registry_names_match_the_classes() -> None:
    for name, cls in READERS.items():
        assert cls.name == name


def test_registry_holds_the_llm_reader() -> None:
    assert "llm" in READERS


def test_empty_pool_grades_to_nothing(query: Query) -> None:
    from graphiv.retrieve.recency import FrontierSpec

    empty = Pool({}, [], FrontierSpec(2025, 2, 2026))
    assert ConstantReader().grade(query, empty) == {}


@pytest.mark.parametrize("relevance", [-2, 0, 2])
def test_constant_reader_accepts_the_whole_relevance_range(
    query: Query, pool: Pool, relevance: int
) -> None:
    got = ConstantReader(relevance=relevance).grade(query, pool)
    assert {g.relevance for g in got.values()} == {relevance}
