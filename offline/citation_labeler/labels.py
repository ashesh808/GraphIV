"""
The citation intent taxonomy and a parser that survives either answer shape

The prompts ask for a json object while the batch instruction asks for numbered lines
The model picks between the two depending on batch size, so both have to parse
"""

from __future__ import annotations

import json
import re
from typing import Any

INTENTS: tuple[str, ...] = ("uses", "extends", "compares", "motivates", "background", "critiques")

_LINE = re.compile(r"\s*(\d+)\s*[:.)-]\s*([A-Za-z]+)\s*[-:]?\s*(.*)")


def _from_json(text: str, count: int) -> list[tuple[str, str] | None] | None:
    """
    Read the `{"labels": [{"id": n, "intent": s}]}` shape the prompts ask for

    Args:
        text: the raw completion.
        count: how many items were sent.

    Returns:
        One (intent, reason) per item, or None when the text is not that shape.
    """
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        blob: dict[str, Any] = json.loads(
            text[start : end + 1]
        )  # pyright: ignore[reportExplicitAny]
    except ValueError:
        return None
    entries = blob.get("labels")  # pyright: ignore[reportAny]
    if not isinstance(entries, list):
        return None

    out: list[tuple[str, str] | None] = [None] * count
    for entry in entries:  # pyright: ignore[reportAny]
        if not isinstance(entry, dict):
            continue
        raw_id, raw_intent = entry.get("id"), entry.get("intent")  # pyright: ignore[reportAny]
        if not isinstance(raw_id, int) or not isinstance(raw_intent, str):
            continue
        name = raw_intent.strip().lower()
        if 0 <= raw_id < count and name in INTENTS:
            out[raw_id] = (name, "")
    return out


def parse_labels(text: str, count: int) -> list[tuple[str, str] | None]:
    """
    Align one completion back onto the items it answered

    An item the model did not answer stays None rather than becoming `background`, since that
    default is itself a valid label and would hide the failure inside the majority class.

    Args:
        text: the raw completion.
        count: how many items were sent.

    Returns:
        One (intent, reason) per item, None where nothing usable came back.
    """
    from_json = _from_json(text, count)
    if from_json is not None and any(x is not None for x in from_json):
        return from_json

    out: list[tuple[str, str] | None] = [None] * count
    for line in text.splitlines():
        hit = _LINE.match(line.strip())
        if not hit:
            continue
        index, name = int(hit.group(1)), hit.group(2).lower()
        if 0 <= index < count and name in INTENTS:
            out[index] = (name, hit.group(3).strip())
    return out
