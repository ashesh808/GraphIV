"""
The gold evaluation battery, loaded from the editable topics.json

Canonical papers and the ordered spine drive recall, and a topic without them skips it
Edit topics.json rather than this file to change or extend the battery
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class GoldTopic:
    key: str
    query: str
    canonical: frozenset[str] = field(default_factory=frozenset)
    spine: tuple[str, ...] = ()


_TOPICS_JSON = Path(__file__).resolve().parent / "topics.json"


def _load() -> dict[str, GoldTopic]:
    raw: dict[str, Any] = json.loads(  # pyright: ignore[reportExplicitAny]
        _TOPICS_JSON.read_text(encoding="utf-8")
    )
    out: dict[str, GoldTopic] = {}
    for key, spec_any in raw.items():
        if key.startswith("_"):
            continue
        spec = cast("dict[str, Any]", spec_any)  # pyright: ignore[reportExplicitAny]
        out[key] = GoldTopic(
            key=key,
            query=str(spec["query"]),
            canonical=frozenset(cast("list[str]", spec.get("canonical", []))),
            spine=tuple(cast("list[str]", spec.get("spine", []))),
        )
    return out


TOPICS: dict[str, GoldTopic] = _load()


def battery() -> list[str]:
    """
    Topic keys a lever runs over: env `EXP_TOPICS` (comma-sep subset) or the whole topics.json
    """
    env = os.environ.get("EXP_TOPICS", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip() in TOPICS]
    return list(TOPICS)


"""
The validation panel for the deep levers: every gold set plus breadth across the design
A deep run is slow, so a mechanism validates here before it widens to the full battery
The cache makes that widening incremental, since these topics are reused and not recomputed
"""
_DEEP_PANEL: tuple[str, ...] = (
    "diffusion",
    "testtime",
    "transformer",
    "gnn",
    "ssm",
    "llm_agents",
    "diffusion_video",
    "gnn_drug",
)


def deep_panel() -> list[str]:
    """
    Topic keys for the deep levers: env `EXP_TOPICS` override, else the 8-topic `_DEEP_PANEL`

        Set `EXP_TOPICS=$(...)` or edit `_DEEP_PANEL`; pass the full battery once validated.
    """
    env = os.environ.get("EXP_TOPICS", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip() in TOPICS]
    return [k for k in _DEEP_PANEL if k in TOPICS]


def recall(meta_landmarks: list[str], topic: GoldTopic) -> dict[str, float]:
    """
    Fraction of canonical + spine ids present among the report's landmarks
    """
    present = {a.lower() for a in meta_landmarks}
    canon = {c.lower() for c in topic.canonical}
    spine = {s.lower() for s in topic.spine}
    lm_recall = len(canon & present) / len(canon) if canon else 0.0
    sp_recall = len(spine & present) / len(spine) if spine else 0.0
    return {
        "landmark_recall": round(lm_recall, 3),
        "spine_recall": round(sp_recall, 3),
    }
