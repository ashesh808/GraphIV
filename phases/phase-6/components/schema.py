"""P2 / R1.5 — propose a question-specific extraction schema.

Instead of a generic 3-sentence digest, the deep-research path asks Gemma what FIELDS are
worth pulling from each paper for THIS question (e.g. diffusion-in-medical -> modality,
anatomy, dataset, metric, result, limitation). The schema is whitelisted (simple field
names, capped count) so the downstream per-paper extraction is structured and comparable.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


from llm import chat_sync, parse_json  # noqa: E402

MODEL = "Gemma-4-26B-Code"
MAX_FIELDS = 8
_NAME_RE: re.Pattern[str] = re.compile(r"[^a-z0-9_]")
_DEFAULT: list[tuple[str, str]] = [
    ("contribution", "the core contribution or claim"),
    ("method", "the technique, architecture, or objective"),
    ("dataset", "datasets or benchmarks used"),
    ("result", "the key quantitative result"),
    ("limitation", "stated limitations or failure modes"),
]


@dataclass
class Schema:
    question: str
    fields: list[tuple[str, str]]  # (name, description)

    @property
    def hash(self) -> str:
        key = self.question + "|" + ",".join(n for n, _ in self.fields)
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def names(self) -> list[str]:
        return [n for n, _ in self.fields]


_SYS = (
    "You design a structured extraction schema for a literature-review question. Given the "
    "question and a few sample papers, list 4-7 FIELDS worth extracting from each paper to "
    "answer it well. Use short snake_case names and a <=10-word description each.\n"
    'Output ONLY JSON: [{"name":"..","description":".."}, ...].'
)


def _clean_name(raw: str) -> str:
    return _NAME_RE.sub("_", raw.strip().lower()).strip("_")[:30]


def propose_schema(question: str, samples: list[str], model: str = MODEL) -> Schema:
    """LLM -> validated Schema; falls back to a generic 5-field schema on failure."""
    ctx = "\n\n".join(samples[:6])
    user = f"QUESTION: {question}\n\nSAMPLE PAPERS:\n{ctx}"
    try:
        text, _, _ = chat_sync(model, _SYS, user, 0.0, 2000)
    except Exception:  # noqa: BLE001
        return Schema(question, _DEFAULT)
    obj = parse_json(text)
    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    if isinstance(obj, list):
        for item in obj:  # pyright: ignore[reportAny]
            if not isinstance(item, dict):
                continue
            name = _clean_name(
                str(item.get("name") or "")
            )  # pyright: ignore[reportAny]
            desc = str(item.get("description") or "")[:80]  # pyright: ignore[reportAny]
            if name and name not in seen:
                seen.add(name)
                fields.append((name, desc))
            if len(fields) >= MAX_FIELDS:
                break
    return Schema(question, fields or _DEFAULT)
