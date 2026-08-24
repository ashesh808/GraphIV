"""
The flagship end-to-end comparison: the deployed pipeline against its predecessor

Unlike the single-lever ablations this is holistic, with every shipped lever on at once
The long reviews and figure galleries are the artifact, and the table only quantifies the jump
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the deep-research flagship dir

RESULTS = _EXP / "results"


def run(_use_cache: bool = True) -> None:
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
        results_dir=RESULTS,
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
        title="deep-research: before vs after (deep panel)",
        do_judge=True,
        do_faith=True,
        do_vision=True,
        pairwise=("after-deep", "before-2023"),
        shared_runs=True,
    )


if __name__ == "__main__":
    run()
