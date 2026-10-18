"""
A freeform interest into the focused questions this corpus can actually answer

The candidates are grounded in real titles, so the model cannot offer a question nothing answers
It asks at most one thing back, and only when the candidates differ on subject rather than on mode
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.core import llm
from src.core.schema import Query
from src.mcp.state import Handles
from src.retrieve.cosine import CosineRetriever

LOG = logging.getLogger(__name__)

PROBE = 20
MODES = ("survey", "frontier")

PROMPT = """You refine a freeform research interest into focused literature questions over arXiv,
grounded in what the corpus actually contains, which the title probe below shows you.

USER INTEREST: {interest}

CORPUS TITLE PROBE:
{probe}

Rules:
- Propose 2 to 4 candidate focused questions the corpus can clearly support.
- Every candidate stays inside the stated scope. Never introduce a subfield, an application
  domain or a combination the user did not mention.
- If the interest is already one focused question, return it as the single candidate.
- Tag every candidate with a mode. "survey" means the answer is the lineage a field is built on,
  so foundational and heavily cited work carries it. "frontier" means the answer is what people
  are doing right now, so recent work carries it.
- When the interest already says which it wants, every candidate takes that mode.
- Only when it genuinely reads both ways, emit one candidate of each mode and let the pick settle
  it rather than asking.
- At most one clarifying question, and only when the candidates differ on subject rather than on
  mode. It must be specific to this topic, never generic.

Reply with json only, no preamble:
{{"candidates": [{{"question": "...", "mode": "survey"}}], "clarifying_question": ""}}
"""


def probe(handles: Handles, text: str, limit: int = PROBE) -> list[str]:
    """
    The titles the corpus holds nearest the interest, which is what grounds the candidates

    Args:
        handles: The shared handles.
        text: The freeform interest.
        limit: How many titles to read.

    Returns:
        One line per paper with its id, ranked by closeness.
    """
    query = Query(text=text, emb=handles.embed(text))
    found = CosineRetriever(handles.dsn).retrieve(query, limit)
    return [f"- {p.arxiv_id} ({p.date.year}) {' '.join(p.title.split())}" for p in found]


def refine(handles: Handles, interest: str) -> str:
    """
    The questions worth asking, each tagged with the mode that answers it

    Args:
        handles: The shared handles.
        interest: What the user said they want.

    Returns:
        The candidates, the one clarifying question and the probe, as json.
    """
    titles = probe(handles, interest)
    reply = handles.model.ask(
        PROMPT.format(interest=interest, probe="\n".join(titles) or "(no titles)"),
        max_tokens=600,
    )
    parsed = llm.parse_json(reply)
    raw = parsed.get("candidates") if isinstance(parsed, dict) else None
    candidates: list[dict[str, str]] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        question = " ".join(str(entry.get("question", "")).split())
        mode = str(entry.get("mode", "survey")).strip().lower()
        if question:
            candidates.append({"question": question, "mode": mode if mode in MODES else "survey"})
    if not candidates:
        candidates = [{"question": interest, "mode": "survey"}]
    asked = str(parsed.get("clarifying_question", "")) if isinstance(parsed, dict) else ""
    out: dict[str, Any] = {
        "candidates": candidates[:4],
        "clarifying_question": " ".join(asked.split()),
        "probe": titles,
    }
    LOG.info("refined into %d candidates", len(out["candidates"]))
    return json.dumps(out, indent=2)
