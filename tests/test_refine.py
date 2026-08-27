"""
The refine-time mode decision: candidate normalization, the fallback classifier and the flag

Nothing here reaches a database or a model, so the model call is replaced with a stub
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from graphiv.retrieve.select import SELECTORS
from graphiv.serve import mcp_server as srv


def _norm(candidates: object) -> list[dict[str, str]]:
    return srv._candidates({"candidates": candidates}, "fallback interest")


def _stub_chat(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    """
    Replace the shared chat helper with one that returns a fixed body

    Args:
        monkeypatch: The pytest patcher.
        reply: The raw model output _classify_mode has to parse.
    """
    import graphiv.core.llm as llm

    async def fake(*_a: object, **_k: object) -> tuple[str, int, int]:
        return reply, 0, 0

    monkeypatch.setattr(llm, "chat", fake)


def test_every_mode_maps_to_a_real_selector() -> None:
    for rank in srv._MODES.values():
        assert rank in SELECTORS


def test_the_default_mode_is_a_mode() -> None:
    assert srv._DEFAULT_MODE in srv._MODES


def test_both_modes_are_described_in_the_refine_prompt() -> None:
    for mode in srv._MODES:
        assert mode in srv._REFINE_SYS
        assert mode in srv._MODE_SYS


def test_candidates_keep_the_mode_the_model_gave() -> None:
    got = _norm([{"question": "what is X built on", "mode": "frontier"}])
    assert got == [{"question": "what is X built on", "mode": "frontier"}]


def test_a_bare_string_candidate_still_parses() -> None:
    """
    The model drifts back to the pre-mode shape under load, which must not lose the question
    """
    assert _norm(["what is X"]) == [{"question": "what is X", "mode": srv._DEFAULT_MODE}]


def test_an_unknown_mode_falls_back() -> None:
    got = _norm([{"question": "q", "mode": "sideways"}])
    assert got[0]["mode"] == srv._DEFAULT_MODE


def test_a_blank_question_is_dropped() -> None:
    got = _norm([{"question": "  ", "mode": "frontier"}, {"question": "real", "mode": "survey"}])
    assert [c["question"] for c in got] == ["real"]


def test_no_usable_candidate_falls_back_to_the_users_text() -> None:
    for raw in ([], "not a list", None, [{"mode": "survey"}]):
        assert _norm(raw) == [{"question": "fallback interest", "mode": srv._DEFAULT_MODE}]


def test_a_missing_candidates_key_falls_back() -> None:
    assert srv._candidates({}, "my interest")[0]["question"] == "my interest"


def test_questions_are_stripped() -> None:
    assert _norm(["  spaced  "])[0]["question"] == "spaced"


def test_the_classifier_takes_the_models_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chat(monkeypatch, '{"mode":"frontier"}')
    assert asyncio.run(srv._classify_mode("what is new in X")) == "frontier"


def test_the_classifier_rejects_an_invented_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chat(monkeypatch, '{"mode":"whatever"}')
    assert asyncio.run(srv._classify_mode("q")) == srv._DEFAULT_MODE


def test_unparseable_output_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chat(monkeypatch, "the model rambled instead")
    assert asyncio.run(srv._classify_mode("q")) == srv._DEFAULT_MODE


def test_a_dead_model_does_not_block_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphiv.core.llm as llm

    async def boom(*_a: object, **_k: object) -> tuple[str, int, int]:
        raise RuntimeError("router down")

    monkeypatch.setattr(llm, "chat", boom)
    assert asyncio.run(srv._classify_mode("q")) == srv._DEFAULT_MODE


def test_a_seeded_run_never_calls_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A raise here would be swallowed by the classifier's own handler, so the call is counted
    """
    import graphiv.core.llm as llm

    calls: list[object] = []

    async def counted(*a: object, **_k: object) -> tuple[str, int, int]:
        calls.append(a)
        return '{"mode":"frontier"}', 0, 0

    monkeypatch.setattr(llm, "chat", counted)
    assert asyncio.run(srv._classify_mode("   ")) == srv._DEFAULT_MODE
    assert calls == []


def _captured_rank(monkeypatch: pytest.MonkeyPatch, **kw: Any) -> str:
    """
    Run deep_research against a stub subprocess and read back the rank flag it launched with

    Args:
        monkeypatch: The pytest patcher.
        kw: Extra keyword arguments for deep_research.

    Returns:
        The value of the --set-rank flag.
    """
    seen: list[str] = []

    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def fake_exec(*args: str, **_k: object) -> FakeProc:
        seen.extend(args)
        return FakeProc()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", fake_exec)
    _ = asyncio.run(srv.deep_research("a question", force_new=True, **kw))
    return next(a.split("=", 1)[1] for a in seen if a.startswith("--set-rank="))


def test_survey_launches_the_joint_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_rank(monkeypatch, mode="survey") == "joint"


def test_frontier_launches_the_trajectory_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_rank(monkeypatch, mode="frontier") == "trajectory"


def test_mode_is_case_and_space_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_rank(monkeypatch, mode="  Frontier ") == "trajectory"


def test_an_unknown_mode_is_reclassified(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chat(monkeypatch, '{"mode":"frontier"}')
    assert _captured_rank(monkeypatch, mode="nonsense") == "trajectory"


def test_an_absent_mode_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chat(monkeypatch, '{"mode":"frontier"}')
    assert _captured_rank(monkeypatch) == "trajectory"
