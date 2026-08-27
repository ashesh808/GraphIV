"""
The judge that reads a draft and decides whether the review is saturated

It owns loop termination, so the effort dial is only an upper cap on rounds
A gap comes back as a concrete query rather than a complaint, which the next round retrieves
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from graphiv.core.llm import THINK, chat_sync
from graphiv.core.models import Landmark

JUDGE_MODEL = "Gemma-4-26B"


def _json_objects(text: str) -> list[str]:
    """
    All top-level brace-balanced {...} substrings, in order

    Robust to thinking-channel
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
    """
    One judge round: saturation, per-axis scores and the gaps still open
    """

    saturated: bool
    scores: dict[str, int] = field(default_factory=dict)  # 1-5 per dimension
    gaps: list[str] = field(default_factory=list)  # follow-up seed queries
    assessment: str = ""

    def mean_score(self) -> float:
        """
        Mean of the per-axis scores, or zero when the judge returned none
        """
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


_SYS = (
    "You are a meticulous senior researcher reviewing a DRAFT literature review for "
    "completeness. You are given the question, the draft, the structured digest of papers it "
    "was built from, and RETRIEVAL CONTEXT describing everything the pipeline found. Judge "
    "the draft on six axes (1-5): grounding (claims trace to cited papers, every arXiv id "
    "has ALREADY been mechanically verified against the corpus, so never judge grounding by "
    "whether an id or its year looks plausible; judge whether CLAIMS match the digest "
    "evidence), coverage (breadth relative to what the RETRIEVAL CONTEXT shows was found, "
    "high-relevance papers left uncited cap coverage), lineage (origins->frontier story is "
    "coherent), coherence (well-organized prose), frontier (genuinely covers the LATEST "
    "work, not just classics), and focus (every section serves THE question; a section spent "
    "on an off-domain subfield or generic background caps focus at 2).\n"
    "Then decide: is the review SATURATED (thorough enough to stop), or are there concrete "
    "GAPS? Gaps may be search queries (short topical phrases) OR specific uncited papers "
    "from the retrieval context, written as 'arXiv:<id>', prefer naming the uncited papers "
    "when they exist. Be demanding: a review missing recent methods, a whole sub-area, or "
    "the named high-relevance uncited papers is NOT saturated.\n"
    "Reason as needed, then end your reply with ONE JSON object on its own line:\n"
    '{"scores":{"grounding":N,"coverage":N,"lineage":N,"coherence":N,"frontier":N,"focus":N},'
    '"saturated":true|false,"gaps":["query or arXiv:<id>", "..."],"assessment":"one sentence"}'
)


def _parse_verdict(text: str) -> Verdict:
    """
    Take the LAST well-formed verdict JSON object (after any thinking/reasoning prose)
    """
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
        gaps = [str(g) for g in raw_gaps if str(g).strip()] if isinstance(raw_gaps, list) else []
        return Verdict(
            saturated=bool(obj.get("saturated")),
            scores=scores,
            gaps=gaps[:4],
            assessment=str(obj.get("assessment") or "")[:300],
        )
    # an unparseable verdict is not saturation, so a parse glitch cannot end the loop early
    return Verdict(saturated=False, assessment="(judge output unparseable)")


def retrieval_context(
    report: str,
    landmarks: list[Landmark],
    frontier_year: int,
    frontier_count: int,
    top_uncited: int = 10,
) -> str:
    """
    Cohort stats + named high-relevance uncited landmarks, the coverage anchor
    """
    roles: dict[str, int] = {}
    for lm in landmarks:
        roles[lm.role or "ungraded"] = roles.get(lm.role or "ungraded", 0) + 1
    cited = [lm for lm in landmarks if f"arXiv:{lm.arxiv_id}" in report]
    uncited = sorted(
        (
            lm
            for lm in landmarks
            if lm.relevance is not None
            and lm.relevance >= 1
            and f"arXiv:{lm.arxiv_id}" not in report
        ),
        key=lambda lm: (-(lm.relevance or 0), -lm.in_degree),
    )
    lines = [
        f"landmarks {len(landmarks)} · draft cites {len(cited)}/{len(landmarks)} · "
        f"frontier_year {frontier_year} · {frontier_count} landmarks at/after it",
        "roles: " + ", ".join(f"{k} {v}" for k, v in sorted(roles.items())),
    ]
    if uncited:
        lines.append("highest-value UNCITED landmarks:")
        for lm in uncited[:top_uncited]:
            lines.append(
                f"  arXiv:{lm.arxiv_id} (rel {lm.relevance}, cited-by {lm.in_degree} "
                f'in-topic) "{lm.title[:70]}"'
            )
    return "\n".join(lines)


def judge_report(
    question: str,
    report: str,
    digest: str,
    frontier_year: int,
    round_idx: int,
    max_rounds: int,
    context: str = "",
) -> Verdict:
    """
    One judging pass (thinking on, -code)

    Returns the saturation/gaps verdict.

        Round 1 of a multi-round run may never saturate, one guaranteed second look is cheap
        insurance against a generous first verdict (observed: instant 5.0 on an uncovered draft).
    """
    ctx = f"\nRETRIEVAL CONTEXT:\n{context}\n" if context else ""
    user = (
        f"QUESTION: {question}\n"
        f"This is round {round_idx + 1} of at most {max_rounds}. The topic's detected "
        f"frontier starts at year {frontier_year}; demand real coverage of {frontier_year}+ "
        f"work.\n{ctx}\nDRAFT REVIEW:\n{report}\n\n---\nDIGEST (paper evidence):"
        f"\n{digest[:12000]}"
    )
    try:
        text, _, _ = chat_sync(JUDGE_MODEL, _SYS, user, 0.3, 4000, extra_body=THINK)
    except Exception as e:  # noqa: BLE001
        print(f"  [judge] error: {type(e).__name__}; stopping loop", flush=True)
        return Verdict(saturated=True, assessment="(judge call failed; stopping)")
    v = _parse_verdict(text)
    if v.saturated and round_idx == 0 and max_rounds > 1:
        v.saturated = False
        v.assessment = "(round-1 saturation overridden, one more look) " + v.assessment
    return v
