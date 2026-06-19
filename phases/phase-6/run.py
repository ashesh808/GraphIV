"""Phase-6 entry point — the research endpoint.

Question in -> grounded, chronological literature report (+ figure gallery on deep) out.
    uv run python phases/phase-6/run.py "<question>" [--set-effort deep] [--set-rank ppr]
                                        [--include-no-cluster] [--include-no-graph] [--dry-run]
Config keys: effort {fast,standard,deep}, rank {ppr,frontier,indegree}, no_cluster, no_graph.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))  # flat imports within components/
sys.path.insert(0, str(_HERE.parent))  # phases/ -> _framework

from _framework import Resolved, print_config, resolve  # noqa: E402

import pipeline  # noqa: E402


def _plan(r: Resolved, question: str) -> None:
    """Print the resolved deep-research plan for --dry-run (no work)."""
    effort: str = r.config["effort"]
    n_pool, target, m, do_extract = pipeline.TIERS[effort]
    print(f"[phase-6] question: {question!r}")
    print(
        f"[phase-6] R1 retrieve: pool={n_pool} drill_target={target} rank={r.config['rank']}"
    )
    print(
        f"[phase-6]   no_cluster={r.config['no_cluster']} no_graph={r.config['no_graph']}"
    )
    print(
        f"[phase-6] landmarks m={m} · R2 full-text extraction={'on' if do_extract else 'off'}"
    )
    print(
        f"[phase-6] R3 compose + figures={'on (top 12)' if effort == 'deep' else 'off'}"
    )
    print(
        f"[phase-6] writes -> {pipeline.OUT}/<slug>/<cfg>/{{report.md,digest.txt,run.json}}"
    )


def main() -> None:
    r = resolve(
        _HERE, sys.argv[1:], required=("effort", "rank", "no_cluster", "no_graph")
    )
    print_config("phase-6", r)
    if not r.positionals:
        raise SystemExit("phase-6 needs a question (positional arg)")
    question = r.positionals[0]
    if r.dry_run:
        _plan(r, question)
        return
    _ = pipeline.run(
        question,
        r.config["effort"],
        r.config["rank"],
        bool(r.config["no_cluster"]),
        bool(r.config["no_graph"]),
    )


if __name__ == "__main__":
    main()
