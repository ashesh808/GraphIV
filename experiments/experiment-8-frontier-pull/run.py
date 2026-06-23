"""experiment-3 — Leaf-independent frontier_pull on/off.

Tests whether the direct, year-filtered vector pull (`retrieval_refined.frontier_pull`) is what
lets brand-new (2026) papers enter the pool, by toggling it off. One variable: `no_frontier_pull`.
Single-pass, fast effort, two topics.

    uv run python experiments/experiment-3-frontier-pull/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import battery  # noqa: E402

HERE = Path(__file__).resolve().parent


def main() -> None:
    conditions = [
        ("on", {"effort": "fast", "recency": 0.6, "no_frontier_pull": False}),
        ("off", {"effort": "fast", "recency": 0.6, "no_frontier_pull": True}),
    ]
    _ = run_experiment(
        results_dir=HERE / "results",
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
        title="experiment-8: leaf-independent frontier_pull on/off (mean over battery)",
    )


if __name__ == "__main__":
    main()
