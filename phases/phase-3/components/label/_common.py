"""Shared paths and helpers for phase_3.label.

The labeling pipeline has two stages:

  1. `sample.py` builds a seed-deterministic stratified sample of (citing_id,
     ordinal) pairs from the citation table and writes the index list to
     `data/citation_labels/sample.txt`.
  2. `teacher.py` reads the index list, fetches the row payload from Postgres
     for each id, and pseudo-labels them via the local Gemma-4-26B teacher,
     writing results into a SQLite db at `data/citation_labels/labels.db`.

A follow-up `student/` package fine-tunes ModernBERT on those labels; its
weights live under `MODELS_DIR` (this module also pins the HF cache there so
nothing leaks into the global `~/.cache/huggingface`).

The schema is intentionally separate from the phase 3 parse Postgres table:
the labeler is a research artifact that may be regenerated multiple times
with different teachers/taxonomies. Once we have a frozen label set, the
labels can be merged back into the `citation.intent` / `intent_score` /
`intent_model` columns in a single COPY.
"""

from __future__ import annotations

import os
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3]))
from _framework import REPO_ROOT as _REPO_ROOT  # noqa: E402
from _framework import pg_dsn as _pg_dsn  # noqa: E402

BASE_PATH: Path = _REPO_ROOT / "data"
ARXIV_SQLITE: Path = BASE_PATH / "metadata" / "arxiv.db"

LABELS_DIR: Path = BASE_PATH / "citation_labels"
SAMPLE_TXT: Path = LABELS_DIR / "sample.txt"
LABELS_DB: Path = LABELS_DIR / "labels.db"

# Trained + untrained model weights all live under MODELS_DIR. HF downloads
# go into HF_CACHE_DIR (a project-local cache); student checkpoints go into
# subdirs like data/models/student-v1/.
MODELS_DIR: Path = BASE_PATH / "models"
HF_CACHE_DIR: Path = MODELS_DIR / "hf_cache"


def pin_hf_cache() -> None:
    """Set HF_HOME / HF_HUB_CACHE to the project-local cache.

    Must be called BEFORE `import transformers` (or any huggingface_hub
    import) so the env vars take effect at module load time.
    """
    HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE_DIR))
    os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))


ARXIVKG_PG_DSN: str = _pg_dsn()

# Taxonomy used by the teacher prompt and validated on parse.
INTENTS: tuple[str, ...] = (
    "uses",
    "extends",
    "compares",
    "motivates",
    "background",
    "critiques",
)
POLARITIES: tuple[str, ...] = ("positive", "neutral", "negative")

# Section bucket labels, ordered by typical position in a paper.
SECTION_BUCKETS: tuple[str, ...] = (
    "intro",
    "related",
    "method",
    "experiment",
    "discussion",
    "other",
)


def section_bucket(section: str | None) -> str:
    """Map a free-text section heading to one of SECTION_BUCKETS.

    The heading text in our citation table is the nearest ancestor <section>
    title produced by LaTeXML, e.g. "1. Introduction", "Related Work",
    "3.2 Architecture", "Conclusions and Future Work". We strip numeric
    prefixes and keyword-match.
    """
    if not section:
        return "other"
    s = section.strip().lower()
    # strip leading numbering ("1.", "1.2.3", "iii.")
    parts = s.split(maxsplit=1)
    if parts and (
        parts[0].rstrip(".").replace(".", "").isdigit()
        or set(parts[0]) <= set("ivxlcdm.")
    ):
        s = parts[1] if len(parts) > 1 else s
    if any(
        k in s
        for k in (
            "introduction",
            "background",
            "preliminaries",
            "overview",
            "motivation",
        )
    ):
        return "intro"
    if any(
        k in s
        for k in ("related work", "prior work", "literature review", "related research")
    ):
        return "related"
    if any(
        k in s
        for k in (
            "method",
            "approach",
            "model",
            "architecture",
            "algorithm",
            "framework",
            "proposed",
            "design",
        )
    ):
        return "method"
    if any(
        k in s
        for k in (
            "experiment",
            "result",
            "evaluation",
            "ablation",
            "benchmark",
            "performance",
            "analysis",
        )
    ):
        return "experiment"
    if any(
        k in s for k in ("discussion", "conclusion", "future", "limitation", "summary")
    ):
        return "discussion"
    return "other"
