"""experiment-7 — Deep-research dogfood (end-to-end before/after).

Unlike experiments 1-6 (single-lever ablations), this is the holistic demonstration: the OLD
hardcoded-2023 single-pass behavior versus the FULL upgraded deep pipeline, on two topics. The
long md/tex reviews + figure galleries under results/runs are the primary artifact; the table
quantifies the jump (2026 coverage, length, grounding, judge, figures).

  before-2023 : single-pass, raw in-degree, recency=0, frontier_pull OFF  (mimics the old default)
  after-deep  : deep judge-loop, ppr, recency=0.5, frontier_pull ON, critique + vision figures

    uv run python experiments/experiment-7-deep-dogfood/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

HERE = Path(__file__).resolve().parent


def main() -> None:
    conditions = [
        (
            "before-2023",
            {
                "effort": "standard",
                "rank": "indegree",
                "recency": 0.0,
                "no_frontier_pull": True,
            },
        ),
        (
            "after-deep",
            {
                "effort": "standard",
                "deep": True,
                "max_rounds": 3,
                "recency": 0.5,
                "rank": "ppr",
                "critique_k": 6,
                "figures": True,
            },
        ),
    ]
    _ = run_experiment(
        results_dir=HERE / "results",
        topic_keys=deep_panel(),
        conditions=conditions,
        label_key="pipeline",
        table_cols=[
            "pipeline",
            "n_topics",
            "n_2026",
            "ge_2025",
            "frontier_count",
            "words",
            "grounded",
            "gold_recall",
            "n_figures",
            "caption_faithfulness",
            "j_coverage",
            "j_lineage",
            "j_overall",
        ],
        plot_metrics=[
            ("n_2026", "2026 landmarks"),
            ("words", "Review length (words)"),
            ("j_coverage", "Judge coverage (1-5)"),
            ("n_figures", "Figures captioned"),
        ],
        title="experiment-12: deep-research dogfood, before vs after (deep panel)",
        do_judge=True,
        do_faith=True,
        do_vision=True,
        pairwise=("after-deep", "before-2023"),
        shared_runs=True,
    )


if __name__ == "__main__":
    main()
