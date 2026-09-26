"""
One question into the areas someone would have to read separately to answer it

A question spanning four fields embeds into a region that is none of them, so the split comes first
Two areas whose method words would be the same are one area, since the retrieval would repeat
"""

from __future__ import annotations

import json
import logging

from src.core import llm
from src.mcp.state import Handles

LOG = logging.getLogger(__name__)

PROMPT = """A researcher asked this.

{question}

Split it into the distinct research areas someone would have to read separately to answer it.

Return json only, no preamble:
{{"areas": [{{"area": "...", "methods": ["...", "..."], "question": "...", "why": "..."}}]}}

Rules:
- Between 2 and {cap} areas, and fewer is better than more.
- "area" names a field as a paper title would phrase it, 4 to 12 words.
- "methods" lists 4 to 8 technical terms a paper in that area would use in its abstract.
- Two areas whose "methods" would be the same are one area, so merge them.
- "question" is what this area alone has to answer, 10 to 25 words.
- "why" says in one sentence what the researcher needs from this area.
- Name no specific papers and no authors.
"""


def anchor(area: str, methods: list[str]) -> str:
    """
    The manufactured document an area is measured against

    The corpus is full of abstracts and a question does not read like one, so the words a paper in
    the area would use are glued into a line that does.

    Args:
        area: The name of the field.
        methods: The method words.

    Returns:
        The line.
    """
    return f"{area}. {', '.join(methods)}" if methods else area


def identify_areas(handles: Handles, question: str, cap: int = 4) -> str:
    """
    The areas one question breaks into, each carrying what it would be retrieved by

    Args:
        handles: The shared handles.
        question: What was asked.
        cap: The most areas to return.

    Returns:
        The areas as json.
    """
    reply = handles.model.ask(PROMPT.format(question=question, cap=cap), max_tokens=900)
    parsed = llm.parse_json(reply)
    raw = parsed.get("areas") if isinstance(parsed, dict) else None
    out: list[dict[str, object]] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        name = " ".join(str(entry.get("area", "")).split())
        methods = [" ".join(str(m).split()) for m in entry.get("methods", []) if str(m).strip()]
        asked = " ".join(str(entry.get("question", "")).split())
        if not name or not asked:
            continue
        out.append(
            {
                "area": name,
                "methods": methods[:8],
                "question": asked,
                "anchor": anchor(name, methods[:8]),
                "why": " ".join(str(entry.get("why", "")).split()),
            }
        )
    if not out:
        out = [{"area": "", "methods": [], "question": question, "anchor": "", "why": ""}]
    LOG.info("split into %d areas", len(out))
    return json.dumps({"areas": out[:cap]}, indent=2)
