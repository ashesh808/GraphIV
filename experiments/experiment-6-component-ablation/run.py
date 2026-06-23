"""experiment-1 — Component ablation study (formalized legacy eval_ablation).

The classic "scientific-paper" ablation: knock out one system component at a time and read the
full metric vector + an independent LLM judge (4-axis) + the faithfulness tripwire. Reproduces the
pre-rewrite finding that no single metric can be trusted (e.g. dropping the citation graph inflates
the frontier count while zeroing edges and destroying chronology).

Conditions (single-pass, two topics):
  full        — refined retrieval + topic tree + full-text extraction + PPR/frontier ranking
  indegree    — replace PPR with raw in-degree (no frontier reservation, no PPR)
  no_cluster  — drop the topic-tree leaf refinement
  no_graph    — drop the citation subgraph (vector-only; no chronology)
  no_fulltext — abstracts only (effort=fast skips per-paper extraction)

    uv run python experiments/experiment-1-component-ablation/run.py
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
        ("full", {"effort": "standard", "rank": "ppr"}),
        ("indegree", {"effort": "standard", "rank": "indegree"}),
        ("no_cluster", {"effort": "standard", "rank": "ppr", "no_cluster": True}),
        ("no_graph", {"effort": "standard", "rank": "ppr", "no_graph": True}),
        ("no_fulltext", {"effort": "fast", "rank": "ppr"}),
    ]
    _ = run_experiment(
        results_dir=HERE / "results",
        topic_keys=battery(),
        conditions=conditions,
        label_key="config",
        table_cols=[
            "config",
            "n_topics",
            "n_landmarks",
            "n_edges",
            "frontier_count",
            "grounded",
            "off_digest",
            "num_density",
            "landmark_recall",
            "j_overall",
            "faithfulness",
        ],
        plot_metrics=[
            ("n_edges", "Citation edges (lineage)"),
            ("frontier_count", "Frontier landmarks"),
            ("off_digest", "Off-digest (lower=better)"),
            ("j_overall", "Judge overall (1-5)"),
        ],
        title="experiment-6: component ablation (mean over battery)",
        do_judge=True,
        do_faith=True,
    )


if __name__ == "__main__":
    main()
