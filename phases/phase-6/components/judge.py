"""LLM-as-judge for the deep-research loop.

Reads the current draft report + its digest and decides whether the literature review is
saturated or what concrete gaps remain (missing subtopics / methods / recent work). The
JUDGE owns loop termination — effort / max-rounds is only an upper cap. Thinking is ON and
the call is routed to the -code model (large ctx + MTP) so the critique reasons over the
whole draft. The returned `gaps` are follow-up seed queries the loop re-retrieves on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from llm import THINK, chat_sync

JUDGE_MODEL = "Gemma-4-26B-Code"


def _json_objects(text: str) -> list[str]:
    """All top-level brace-balanced {...} substrings, in order. Robust to thinking-channel
    braces (a greedy regex would swallow everything between the first and last brace).
    """
    objs: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                objs.append(text[start : i + 1])
    return objs


@dataclass
class Verdict:
    saturated: bool
    scores: dict[str, int] = field(default_factory=dict)  # 1-5 per dimension
    gaps: list[str] = field(default_factory=list)  # follow-up seed queries
    assessment: str = ""

    def mean_score(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


_SYS = (
    "You are a meticulous senior researcher reviewing a DRAFT literature review for "
    "completeness. You are given the question, the draft, and the structured digest of "
    "papers it was built from. Judge it on five axes (1-5): grounding (claims trace to cited "
    "papers), coverage (breadth of the subfield), lineage (origins->frontier story is "
    "coherent), coherence (well-organized prose), and frontier (genuinely covers the LATEST "
    "work, not just classics).\n"
    "Then decide: is the review SATURATED (thorough enough to stop), or are there concrete "
    "GAPS? If gaps, list up to 4 specific follow-up search queries (short topical phrases) "
    "that would retrieve the missing papers — prefer ones targeting under-covered recent "
    "directions. Be demanding: a review missing recent methods or a whole sub-area is NOT "
    "saturated.\n"
    "Reason as needed, then end your reply with ONE JSON object on its own line:\n"
    '{"scores":{"grounding":N,"coverage":N,"lineage":N,"coherence":N,"frontier":N},'
    '"saturated":true|false,"gaps":["query 1","query 2"],"assessment":"one sentence"}'
)


def _parse_verdict(text: str) -> Verdict:
    """Take the LAST well-formed verdict JSON object (after any thinking/reasoning prose)."""
    for frag in reversed(_json_objects(text)):
        try:
            obj = json.loads(frag)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(obj, dict) or "saturated" not in obj:
            continue
        raw_scores = obj.get("scores") or {}
        scores: dict[str, int] = {}
        if isinstance(raw_scores, dict):
            for k, v in raw_scores.items():  # pyright: ignore[reportAny]
                try:
                    scores[str(k)] = int(v)
                except Exception:  # noqa: BLE001
                    pass
        raw_gaps = obj.get("gaps") or []
        gaps = (
            [str(g) for g in raw_gaps if str(g).strip()]
            if isinstance(raw_gaps, list)
            else []
        )
        return Verdict(
            saturated=bool(obj.get("saturated")),
            scores=scores,
            gaps=gaps[:4],
            assessment=str(obj.get("assessment") or "")[:300],
        )
    # unparseable -> NOT saturated, so a parse glitch doesn't masquerade as "done"; the
    # round cap still bounds the loop.
    return Verdict(saturated=False, assessment="(judge output unparseable)")


def judge_report(
    question: str,
    report: str,
    digest: str,
    frontier_year: int,
    round_idx: int,
    max_rounds: int,
) -> Verdict:
    """One judging pass (thinking on, -code). Returns the saturation/gaps verdict."""
    user = (
        f"QUESTION: {question}\n"
        f"This is round {round_idx + 1} of at most {max_rounds}. The topic's detected "
        f"frontier starts at year {frontier_year}; demand real coverage of {frontier_year}+ "
        f"work.\n\nDRAFT REVIEW:\n{report}\n\n---\nDIGEST (paper evidence):\n{digest[:12000]}"
    )
    try:
        text, _, _ = chat_sync(JUDGE_MODEL, _SYS, user, 0.3, 4000, extra_body=THINK)
    except Exception as e:  # noqa: BLE001
        print(f"  [judge] error: {type(e).__name__}; stopping loop", flush=True)
        return Verdict(saturated=True, assessment="(judge call failed; stopping)")
    return _parse_verdict(text)
