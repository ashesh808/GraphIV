"""
Extract the metric vector from one run, never a single number

Any one metric is gameable, so coverage, grounding, specificity and length are read together
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_DIGIT = re.compile(r"\d")


def num_density(report_text: str) -> float:
    """
    Digits per 1000 chars — a cheap specificity proxy (legacy `num_density`)

        A review that states concrete numbers (accuracies, step counts, dataset sizes) scores higher
        than one that hand-waves. Not a quality score on its own; part of the vector.
    """
    n = len(report_text)
    return 1000.0 * len(_DIGIT.findall(report_text)) / n if n else 0.0


def year_histogram(landmarks: list[dict[str, Any]]) -> dict[int, int]:
    return dict(Counter(int(lm["year"]) for lm in landmarks if lm.get("year") is not None))


def metric_vector(meta: dict[str, Any], report_text: str = "") -> dict[str, Any]:
    """
    Flatten a run.json `meta` (+ report text) into a comparable metric row
    """
    lms: list[dict[str, Any]] = meta.get("landmarks", [])
    fy = int(meta.get("frontier_year", 0) or 0)
    ge_2024 = sum(1 for lm in lms if (lm.get("year") or 0) >= 2024)
    ge_2025 = sum(1 for lm in lms if (lm.get("year") or 0) >= 2025)
    n_2026 = sum(1 for lm in lms if (lm.get("year") or 0) == 2026)
    words = len(report_text.split()) if report_text else 0
    row: dict[str, Any] = {
        "n_landmarks": meta.get("n_landmarks"),
        "n_edges": meta.get("n_edges"),
        "frontier_year": fy,
        "frontier_count": meta.get("frontier_count"),
        "ge_2024": ge_2024,
        "ge_2025": ge_2025,
        "n_2026": n_2026,
        "grounded": len(meta.get("grounded", [])),
        "off_digest": len(meta.get("off_digest", [])),
        "report_chars": meta.get("report_chars"),
        "words": words,
        "num_density": round(num_density(report_text), 1) if report_text else None,
        "rounds_run": meta.get("rounds_run"),
        "n_critiques": meta.get("n_critiques"),
        "n_figures": meta.get("n_figures"),
    }
    js = meta.get("judge_scores_final") or {}
    if isinstance(js, dict):
        for k, v in js.items():
            row[f"judge_{k}"] = v
    return row


def load_run(out_dir: Path) -> tuple[dict[str, Any], str]:
    """
    Read run.json + report.md from a phase-6 output dir
    """
    meta: dict[str, Any] = json.loads((out_dir / "run.json").read_text())
    rp = out_dir / "report.md"
    report = rp.read_text() if rp.exists() else ""
    return meta, report


def write_table(rows: list[dict[str, Any]], cols: list[str], path: Path) -> None:
    """
    Write a markdown metric table (one row per condition)
    """
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [head, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    _ = path.write_text("\n".join(lines) + "\n", encoding="utf-8")
