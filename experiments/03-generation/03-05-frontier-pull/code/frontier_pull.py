"""
Whether the year-filtered pull is what lets brand-new papers enter the pool

One variable, toggled off, with the rest of the pipeline unchanged
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import battery  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"


def run(_use_cache: bool = True) -> None:
    conditions = [
        ("on", {"effort": "fast", "recency": 0.6, "no_frontier_pull": False}),
        ("off", {"effort": "fast", "recency": 0.6, "no_frontier_pull": True}),
    ]
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=battery(),
        conditions=conditions,
        label_key="frontier_pull",
        table_cols=[
            "frontier_pull",
            "n_topics",
            "n_2026",
            "ge_2025",
            "frontier_count",
            "n_landmarks",
            "grounded",
            "landmark_recall",
        ],
        plot_metrics=[
            ("n_2026", "2026 landmarks"),
            ("ge_2025", ">= 2025 landmarks"),
            ("frontier_count", "Frontier landmarks"),
            ("grounded", "Grounded citations"),
        ],
        title="03-05: leaf-independent frontier_pull on/off (mean over battery)",
    )


if __name__ == "__main__":
    run()
