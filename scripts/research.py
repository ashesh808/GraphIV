"""
The research endpoint: a question in, a grounded chronological review out

effort is one 0-5 dial over the pool tier, the loop, judge rounds, critique depth and figures
A per-knob flag still wins over it, and effort 3 and up runs the judge-driven deep loop.
"""

from __future__ import annotations

import sys

from graphiv.core.cli import Resolved, print_config, resolve
from graphiv.generate import pipeline

STAGE = "research"


def _effort_settings(r: Resolved, argv: list[str]) -> tuple[str, int, int, bool]:
    """
    Resolve effort into (tier_key, max_rounds, critique_k, figures), with explicit flags winning
    """
    tier_key, p_rounds, p_critique, p_figures = pipeline.effort_profile(r.config["effort"])
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
    """
    Print the resolved research plan for --dry-run, doing no work
    """
    tier_key, max_rounds, critique_k, figures = _effort_settings(r, sys.argv[1:])
    n_pool, target, m, do_extract = pipeline.tier_budget(tier_key, str(r.config["rank"]))
    print(f"[research] question: {question!r}")
    print(
        f"[research] effort={r.config['effort']} -> tier={tier_key} rounds={max_rounds} "
        f"critique_k={critique_k} figures={figures}"
    )
    print(f"[research] R1 retrieve: pool={n_pool} drill_target={target} rank={r.config['rank']}")
    print(
        f"[research]   no_cluster={r.config['no_cluster']} no_graph={r.config['no_graph']} "
        f"recency={r.config['recency']} (frontier year auto-detected per topic)"
    )
    print(f"[research] landmarks m={m} · R2 full-text extraction={'on' if do_extract else 'off'}")
    if max_rounds > 1:
        print(
            f"[research] DEEP LOOP: judge-driven, cap {max_rounds} rounds, "
            f"critique_k={critique_k}, figures={'on' if figures else 'off'}; "
            "thinking on the large-context model; emits report.md + report.tex"
        )
    print(f"[research] writes -> {pipeline.OUT}/<slug>/<cfg>/{{report.md,digest.txt,run.json}}")


def main() -> None:
    """
    Resolve the config, then run either the single pass or the deep loop
    """
    r = resolve(
        STAGE,
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
            "no_grade",
            "fuse",
            "max_date",
            "exclude",
        ),
    )
    print_config(STAGE, r)
    seed = str(r.config.get("seed", "")).strip() or None
    if not r.positionals and not seed:
        raise SystemExit("research needs a question (positional arg) or --set-seed <id>")
    question = r.positionals[0] if r.positionals else ""
    if r.dry_run:
        _plan(r, question)
        return
    from graphiv.download import fetch

    # --set-fetch false/0/off all disable (values arrive as strings or ints)
    fetch.set_enabled(str(r.config.get("fetch", True)).lower() not in ("false", "0", "off"))
    tier_key, max_rounds, critique_k, figures = _effort_settings(r, sys.argv[1:])
    # max_rounds > 1 -> judge-driven deep loop (PDF critique + md/tex); else the single pass
    if max_rounds > 1:
        from graphiv.generate import loop

        _ = loop.run_deep(
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
            no_grade=bool(r.config["no_grade"]),
            fuse=bool(r.config["fuse"]),
            seed=seed,
            max_date=str(r.config["max_date"]),
            exclude=str(r.config["exclude"]),
            preset=str(r.config.get("preset", "")),
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
        no_grade=bool(r.config["no_grade"]),
        fuse=bool(r.config["fuse"]),
        seed=seed,
        max_date=str(r.config["max_date"]),
        exclude=str(r.config["exclude"]),
        preset=str(r.config.get("preset", "")),
    )


if __name__ == "__main__":
    main()
