"""Phase-6 entry point — the research endpoint.

Question in -> grounded, chronological literature report (+ figure gallery at higher effort) out.
    uv run python phases/phase-6/run.py "<question>" [--set-effort 4] [--set-rank ppr]
                                        [--set-recency 0.4] [--include-no-cluster]
                                        [--include-no-graph] [--dry-run]
effort is a single 0-5 master dial (fast/standard/deep alias to 1/2/4): it sets the pool tier,
single-vs-deep loop, judge rounds, critique depth, and figures. 0=instant .. 5=exhaustive; 3+ is
the judge-driven deep loop. Per-knob overrides still win (--set-max-rounds / --set-critique-k /
--include-figures). Other keys: rank {ppr,frontier,indegree}, no_cluster, no_graph, recency
(0..1 frontier emphasis; the frontier year itself is detected per-topic).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))  # flat imports within components/
sys.path.insert(0, str(_HERE.parent))  # phases/ -> _framework

from _framework import Resolved, print_config, resolve  # noqa: E402

import pipeline  # noqa: E402


def _effort_settings(r: Resolved, argv: list[str]) -> tuple[str, int, int, bool]:
    """Resolve numeric/string effort -> (tier_key, max_rounds, critique_k, figures); explicit flags win."""
    tier_key, p_rounds, p_critique, p_figures = pipeline.effort_profile(
        r.config["effort"]
    )
    rounds = (
        int(r.config["max_rounds"])
        if any(a.startswith("--set-max-rounds") for a in argv)
        else p_rounds
    )
    critique = (
        int(r.config["critique_k"])
        if any(a.startswith("--set-critique-k") for a in argv)
        else p_critique
    )
    figures = (
        True
        if "--include-figures" in argv
        else (False if "--include-no-figures" in argv else p_figures)
    )
    return tier_key, rounds, critique, figures


def _plan(r: Resolved, question: str) -> None:
    """Print the resolved deep-research plan for --dry-run (no work)."""
    tier_key, max_rounds, critique_k, figures = _effort_settings(r, sys.argv[1:])
    n_pool, target, m, do_extract = pipeline.TIERS[tier_key]
    print(f"[phase-6] question: {question!r}")
    print(
        f"[phase-6] effort={r.config['effort']} -> tier={tier_key} rounds={max_rounds} "
        f"critique_k={critique_k} figures={figures}"
    )
    print(
        f"[phase-6] R1 retrieve: pool={n_pool} drill_target={target} rank={r.config['rank']}"
    )
    print(
        f"[phase-6]   no_cluster={r.config['no_cluster']} no_graph={r.config['no_graph']} "
        f"recency={r.config['recency']} (frontier year auto-detected per topic)"
    )
    print(
        f"[phase-6] landmarks m={m} · R2 full-text extraction={'on' if do_extract else 'off'}"
    )
    if max_rounds > 1:
        print(
            f"[phase-6] DEEP LOOP: judge-driven, cap {max_rounds} rounds, "
            f"critique_k={critique_k}, figures={'on' if figures else 'off'}; "
            "thinking on -code; emits report.md + report.tex"
        )
    print(
        f"[phase-6] writes -> {pipeline.OUT}/<slug>/<cfg>/{{report.md,digest.txt,run.json}}"
    )


def main() -> None:
    r = resolve(
        _HERE,
        sys.argv[1:],
        required=(
            "effort",
            "rank",
            "no_cluster",
            "no_graph",
            "recency",
            "max_rounds",
            "critique_k",
            "figures",
            "no_frontier_pull",
            "embed_mode",
            "use_hyde",
        ),
    )
    print_config("phase-6", r)
    if not r.positionals:
        raise SystemExit("phase-6 needs a question (positional arg)")
    question = r.positionals[0]
    if r.dry_run:
        _plan(r, question)
        return
    tier_key, max_rounds, critique_k, figures = _effort_settings(r, sys.argv[1:])
    # max_rounds > 1 -> judge-driven deep loop (PDF critique + md/tex); else the single pass.
    if max_rounds > 1:
        import deep_loop  # noqa: PLC0415

        _ = deep_loop.run_deep(
            question,
            tier_key,
            str(r.config["rank"]),
            bool(r.config["no_cluster"]),
            bool(r.config["no_graph"]),
            float(r.config["recency"]),
            max_rounds,
            critique_k,
            figures,
            bool(r.config["no_frontier_pull"]),
            embed_mode=str(r.config["embed_mode"]),
            use_hyde=bool(r.config["use_hyde"]),
        )
        return
    _ = pipeline.run(
        question,
        tier_key,
        str(r.config["rank"]),
        bool(r.config["no_cluster"]),
        bool(r.config["no_graph"]),
        float(r.config["recency"]),
        bool(r.config["no_frontier_pull"]),
        str(r.config["embed_mode"]),
        bool(r.config["use_hyde"]),
    )


if __name__ == "__main__":
    main()
