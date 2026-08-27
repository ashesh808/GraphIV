"""
Assembling a retriever from stage names, and what an unknown name does

The pipeline runs against a stub pool builder, so no test here opens a database
"""

from __future__ import annotations

import pytest

from graphiv.retrieve.api import Pool, Query, Retrieved
from graphiv.retrieve.build import PRESETS, Pipeline, build, from_preset
from graphiv.retrieve.readers import ConstantReader, NullReader
from graphiv.retrieve.select import NamedSelector


class StubPool:
    """
    Hands back a pool built by the fixtures rather than by the database
    """

    name = "stub"

    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    def build(self, q: Query) -> Pool:
        """
        The fixture pool, ignoring the query
        """
        _ = q
        return self.pool


def test_pipeline_name_records_all_three_stages(pool: Pool) -> None:
    p = Pipeline(StubPool(pool), NullReader(), NamedSelector("joint"))
    assert p.name == "stub+null+joint"


def test_pipeline_returns_the_budget(pool: Pool, query: Query) -> None:
    got: Retrieved = Pipeline(StubPool(pool), ConstantReader(), NamedSelector("joint")).retrieve(
        query
    )
    assert len(got.papers) == query.budget


def test_pipeline_carries_the_evidence_back(pool: Pool, query: Query) -> None:
    got = Pipeline(StubPool(pool), ConstantReader(), NamedSelector("frontier")).retrieve(query)
    assert got.pool == pool.nodes
    assert got.edges == pool.edges
    assert got.leaf == "test-leaf"
    assert got.grades


def test_null_reader_leaves_the_grades_empty(pool: Pool, query: Query) -> None:
    got = Pipeline(StubPool(pool), NullReader(), NamedSelector("topk")).retrieve(query)
    assert got.grades == {}


def test_trace_records_every_stage(pool: Pool, query: Query) -> None:
    got = Pipeline(StubPool(pool), ConstantReader(), NamedSelector("joint")).retrieve(query)
    assert set(got.trace) == {
        "pool",
        "edges",
        "graded",
        "pool_seconds",
        "read_seconds",
        "select_seconds",
    }
    assert got.trace["pool"] == len(pool.nodes)


def test_swapping_the_selector_changes_the_answer(pool: Pool, query: Query) -> None:
    a = Pipeline(StubPool(pool), ConstantReader(), NamedSelector("indegree")).retrieve(query)
    b = Pipeline(StubPool(pool), ConstantReader(), NamedSelector("topk")).retrieve(query)
    assert [p.arxiv_id for p in a.papers] != [p.arxiv_id for p in b.papers]


def test_build_rejects_an_unknown_stage() -> None:
    for bad in (("nope", "llm", "joint"), ("graph", "nope", "joint"), ("graph", "llm", "nope")):
        with pytest.raises(KeyError):
            _ = build(*bad)


def test_every_preset_names_registered_stages() -> None:
    from graphiv.retrieve.pools import POOLS
    from graphiv.retrieve.readers import READERS
    from graphiv.retrieve.select import SELECTORS

    for rank, (pool_name, reader, selector) in PRESETS.items():
        assert pool_name in POOLS, rank
        assert reader in READERS, rank
        assert selector in SELECTORS, rank


def test_unknown_preset_raises() -> None:
    with pytest.raises(KeyError):
        _ = from_preset("does-not-exist")


def test_the_llm_free_preset_uses_no_endpoint() -> None:
    assert PRESETS["llmfree"][1] == "constant"


def test_survey_carries_more_landmarks_than_frontier() -> None:
    from graphiv.generate.pipeline import tier_budget

    for effort in ("tiny", "fast", "standard", "deep"):
        survey = tier_budget(effort, "joint")[2]
        frontier = tier_budget(effort, "trajectory")[2]
        assert survey > frontier, effort


def test_the_round_budget_never_erases_the_mode_split() -> None:
    """
    A flat ceiling used to pull a 200-paper survey and a 120-paper frontier run within 20
    """
    from graphiv.generate.loop import round_budget
    from graphiv.generate.pipeline import tier_budget

    for effort in ("fast", "standard", "deep"):
        s0 = tier_budget(effort, "joint")[2]
        f0 = tier_budget(effort, "trajectory")[2]
        for r in range(8):
            assert round_budget(s0, r) > round_budget(f0, r), (effort, r)


def test_the_round_budget_grows_then_settles() -> None:
    from graphiv.generate.loop import round_budget

    seq = [round_budget(120, r) for r in range(8)]
    assert seq[0] == 120
    assert seq == sorted(seq)
    assert seq[-1] == seq[-2]


def test_the_round_budget_respects_the_context_ceiling() -> None:
    from graphiv.generate.loop import M_MAX, round_budget

    assert round_budget(1000, 9) == M_MAX
