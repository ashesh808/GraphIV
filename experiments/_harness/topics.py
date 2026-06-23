"""Gold evaluation topics — loaded from the editable `topics.json` battery.

`canonical` (landmarks a good review must mention) + `spine` (ordered foundational lineage, oldest
-> newest) drive the recall metrics; topics without them simply skip recall. Edit `topics.json`
(not this file) to change/extend the battery. Kept comparable across experiments so caches stay warm.
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
    """Topic keys a lever runs over: env `EXP_TOPICS` (comma-sep subset) or the whole topics.json."""
    env = os.environ.get("EXP_TOPICS", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip() in TOPICS]
    return list(TOPICS)


# 8-topic validation panel for the DEEP levers (9-12): all 3 gold sets + breadth across the design
# (foundational/frontier/compositional). Deep runs are ~10 min each, so mechanism levers validate
# here first; widen to the full battery only once the instruments discriminate. Cache makes scaling
# to 27 strictly incremental (these 8 are reused, not recomputed).
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
    """Topic keys for the deep levers: env `EXP_TOPICS` override, else the 8-topic `_DEEP_PANEL`.

    Set `EXP_TOPICS=$(...)` or edit `_DEEP_PANEL`; pass the full battery once validated.
    """
    env = os.environ.get("EXP_TOPICS", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip() in TOPICS]
    return [k for k in _DEEP_PANEL if k in TOPICS]


def recall(meta_landmarks: list[str], topic: GoldTopic) -> dict[str, float]:
    """Fraction of canonical + spine ids present among the report's landmarks."""
    present = {a.lower() for a in meta_landmarks}
    canon = {c.lower() for c in topic.canonical}
    spine = {s.lower() for s in topic.spine}
    lm_recall = len(canon & present) / len(canon) if canon else 0.0
    sp_recall = len(spine & present) / len(spine) if spine else 0.0
    return {
        "landmark_recall": round(lm_recall, 3),
        "spine_recall": round(sp_recall, 3),
    }
