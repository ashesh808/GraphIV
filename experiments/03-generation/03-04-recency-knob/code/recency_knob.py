"""experiment 03-04 — Topic-adaptive recency knob sweep.

Sweeps `--set-recency` ∈ {0.0, 0.2, 0.4, 0.6, 0.8} over two topics (single-pass, fast effort),
holding everything else constant, and measures how the knob trades historical lineage (citation
edges) against frontier coverage (recent-year landmarks). Populates results/.

    uv run python experiments/03-generation/03-04-recency-knob/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
sys.path.insert(0, str(_HERE.parents[3]))  # experiments/ -> _harness

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import battery  # noqa: E402

RESULTS = _EXP / "results"


def run(_use_cache: bool = True) -> None:
    conditions = [
        (str(r), {"effort": "fast", "recency": r}) for r in (0.0, 0.2, 0.4, 0.6, 0.8)
    ]
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=battery(),
        conditions=conditions,
        label_key="recency",
        table_cols=[
            "recency",
            "n_topics",
            "frontier_count",
            "ge_2025",
            "n_2026",
            "n_edges",
            "grounded",
            "off_digest",
            "landmark_recall",
        ],
        plot_metrics=[
            ("frontier_count", "Frontier landmarks (>= detected year)"),
            ("n_2026", "2026 landmarks"),
            ("n_edges", "Citation edges (lineage proxy)"),
            ("off_digest", "Off-digest citations (lower=better)"),
        ],
        title="03-04: recency knob sweep (mean over battery)",
    )


if __name__ == "__main__":
    run()
