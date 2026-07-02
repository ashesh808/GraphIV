"""LLM-as-judge for generated reviews (ported from the pre-rewrite kg_rag_lab/judge.py).

Four 1-5 axes — grounding, coverage, lineage, coherence — plus a one-paragraph critique. Runs
on Gemma-4-26B (the legacy work found it the most discriminating judge). Averaged over `passes`
to cut single-sample noise. This is the primary quality instrument; faithfulness is the safety
tripwire (separate module).
"""

from __future__ import annotations

from typing import Any

from ._boot import JUDGE_MODEL
from ._llm import chat, parse_json

_AXES = ("grounding", "coverage", "lineage", "coherence")

_SYS = (
    "You are a strict reviewer of research-trajectory literature reviews built from a citation "
    "graph. You are given the TOPIC, a list of CANONICAL arXiv ids a good answer should cover, "
    "and the REVIEW. Give four INTEGER scores, each 1-5 (1=poor, 3=adequate, 5=excellent). Use "
    "the 1-5 scale only, never raw counts.\n"
    "- grounding: claims are specific and attributed to arXiv ids, no vague filler.\n"
    "- coverage: how completely the canonical works AND their roles are represented.\n"
    "- lineage: correct chronological/causal development (origins -> advances -> frontier).\n"
    "- coherence: reads as a clear, flowing, well-structured review.\n"
    "Then a one-paragraph critique (<=600 chars) naming concrete gaps.\n"
    'Output ONLY JSON: {"grounding":N,"coverage":N,"lineage":N,"coherence":N,"critique":"..."}.'
)


def _clamp(v: Any) -> int:  # pyright: ignore[reportAny]
    try:
        return max(1, min(5, int(v)))
    except Exception:  # noqa: BLE001
        return 3


def _judge_once(question: str, report: str, canonical: list[str]) -> dict[str, Any]:
    user = (
        f"TOPIC: {question}\nCANONICAL arXiv ids: {', '.join(canonical) or '(none given)'}\n\n"
        f"REVIEW:\n{report[:32768]}"
    )
    txt = chat(JUDGE_MODEL, _SYS, user, temperature=0.0, max_tokens=2000)
    obj = parse_json(txt)
    if not isinstance(obj, dict):
        return {a: 3 for a in _AXES} | {"critique": "(unparseable judge output)"}
    out: dict[str, Any] = {a: _clamp(obj.get(a)) for a in _AXES}
    out["critique"] = str(obj.get("critique") or "")[:600]
    return out


def judge_report(
    question: str, report: str, canonical: list[str] | None = None, passes: int = 2
) -> dict[str, Any]:
    """Average `passes` judgments. Returns the 4 axes + overall mean + last critique."""
    canonical = canonical or []
    runs = [_judge_once(question, report, canonical) for _ in range(max(1, passes))]
    avg: dict[str, Any] = {}
    for a in _AXES:
        avg[a] = round(sum(float(r[a]) for r in runs) / len(runs), 2)
    avg["overall"] = round(sum(avg[a] for a in _AXES) / len(_AXES), 2)
    avg["critique"] = runs[-1]["critique"]
    avg["passes"] = len(runs)
    return avg


_PAIR_SYS = (
    "You compare TWO research-trajectory literature reviews (A and B) on the SAME topic, built "
    "from a citation graph. The absolute quality is high for both; your job is to pick the BETTER "
    "one on each axis even when the margin is small. Axes: grounding (specific, arXiv-attributed "
    "claims), coverage (completeness over the canonical works and their roles), lineage (correct "
    "origins->advances->frontier development). For each axis answer 'A', 'B', or 'tie'. Then an "
    "overall winner.\n"
    'Output ONLY JSON: {"grounding":"A|B|tie","coverage":"A|B|tie","lineage":"A|B|tie",'
    '"overall":"A|B|tie"}.'
)


def _pair_once(question: str, a: str, b: str, canonical: list[str]) -> dict[str, str]:
    user = (
        f"TOPIC: {question}\nCANONICAL arXiv ids: {', '.join(canonical) or '(none given)'}\n\n"
        f"REVIEW A:\n{a[:32768]}\n\nREVIEW B:\n{b[:32768]}"
    )
    txt = chat(JUDGE_MODEL, _PAIR_SYS, user, temperature=0.0, max_tokens=4000)
    obj = parse_json(txt)
    keys = ("grounding", "coverage", "lineage", "overall")
    if not isinstance(obj, dict):
        return {k: "tie" for k in keys}
    out: dict[str, str] = {}
    for k in keys:
        v = str(obj.get(k, "tie")).strip().upper()[:1]
        out[k] = "A" if v == "A" else "B" if v == "B" else "tie"
    return out


def judge_pairwise(
    question: str, report_a: str, report_b: str, canonical: list[str] | None = None
) -> dict[str, str]:
    """Pairwise A-vs-B preference per axis (A=top condition, B=baseline). Order-debiased by also
    judging B-vs-A and merging; a flipped verdict between the two passes becomes a 'tie'.
    """
    canonical = canonical or []
    fwd = _pair_once(question, report_a, report_b, canonical)
    rev = _pair_once(question, report_b, report_a, canonical)  # A/B swapped
    flip = {"A": "B", "B": "A", "tie": "tie"}
    out: dict[str, str] = {}
    for k in ("grounding", "coverage", "lineage", "overall"):
        r = flip[rev[k]]  # map reverse-pass verdict back to original A/B labels
        out[k] = fwd[k] if fwd[k] == r else "tie"
    return out


# ---------------------------------------------------------------------------
# Per-paper RELEVANCE role (precision instrument): foundational / core / frontier /
# peripheral / unrelated. Used as a metric (exp-15) and as a selection filter (exp-16/selection).
# Judges by content (title+year+abstract) only — independent of our PPR/centrality scores. The
# 5-label prompt was copy-pasted across exp-15/16 + scratchpads; this is the canonical version.

ROLE_LABELS: tuple[str, ...] = (
    "foundational",
    "core",
    "frontier",
    "peripheral",
    "unrelated",
)

_ROLE_SYS = (
    "You categorize ONE research paper by its ROLE relative to a TOPIC. Given the topic and the "
    "paper's title, year, and abstract, assign exactly one label: foundational (seminal origin), "
    "core (central widely-built-on method), frontier (recent leading edge), peripheral (related but "
    "tangential: adjacent-domain application / survey / benchmark), unrelated (off-topic for THIS "
    "topic). Judge by content, not fame. "
    'Output ONLY JSON: {"label":"<one of the five>"}.'
)


def role_judge(
    question: str, arxiv_id: str, title: str, year: int | None, abstract: str
) -> str:
    """One of ROLE_LABELS for this paper relative to `question` (defaults to 'peripheral' on a
    miss). Independent of retrieval scores; caching is the caller's responsibility."""
    user = (
        f"TOPIC: {question}\n\nPAPER\ntitle: {title}\n"
        f"year: {year if year is not None else '?'}\narXiv: {arxiv_id}\n"
        f"abstract: {abstract[:3000] or '(abstract unavailable)'}"
    )
    obj = parse_json(chat(JUDGE_MODEL, _ROLE_SYS, user, temperature=0.0, max_tokens=80))
    label = str(obj.get("label", "")).strip().lower() if isinstance(obj, dict) else ""
    return label if label in ROLE_LABELS else "peripheral"
