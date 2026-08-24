"""
Shared paths, label taxonomy and section buckets for the labeling package

corpus_sample.py writes the sample index and teacher.py labels it into labels.db
"""

from __future__ import annotations

import os
from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

BASE_PATH: Path = _C.data_dir
ARXIV_SQLITE: Path = _C.sqlite_db

LABELS_DIR: Path = _C.citation_labels
SAMPLE_TXT: Path = LABELS_DIR / "sample.txt"
LABELS_DB: Path = LABELS_DIR / "labels.db"

"""
Every model weight lives under the project models directory
HuggingFace downloads land in the project-local cache, never the global one
"""
MODELS_DIR: Path = _C.models_dir
HF_CACHE_DIR: Path = _C.hf_cache


def pin_hf_cache() -> None:
    """
    Set HF_HOME / HF_HUB_CACHE to the project-local cache

        Must be called BEFORE `import transformers` (or any huggingface_hub
        import) so the env vars take effect at module load time.
    """
    HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE_DIR))
    os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))


ARXIVKG_PG_DSN: str = _C.pg_dsn

# Taxonomy used by the teacher prompt and validated on parse
INTENTS: tuple[str, ...] = (
    "uses",
    "extends",
    "compares",
    "motivates",
    "background",
    "critiques",
)

# Section bucket labels, ordered by typical position in a paper
SECTION_BUCKETS: tuple[str, ...] = (
    "intro",
    "related",
    "method",
    "experiment",
    "discussion",
    "other",
)


def section_bucket(section: str | None) -> str:
    """
    Map a free-text section heading to one of SECTION_BUCKETS

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
        parts[0].rstrip(".").replace(".", "").isdigit() or set(parts[0]) <= set("ivxlcdm.")
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
    if any(k in s for k in ("related work", "prior work", "literature review", "related research")):
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
    if any(k in s for k in ("discussion", "conclusion", "future", "limitation", "summary")):
        return "discussion"
    return "other"
