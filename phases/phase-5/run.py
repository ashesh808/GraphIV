"""Phase-5 entry point — build the semantic index (preprocessing).

Components:
  topic_tree        — bisecting density-aware tree over UMAP-50 nomic vectors -> TOPIC_TREE_DB
  community_summary — (--include-summaries) per-leaf LLM topic labels -> COMMUNITY_SUMMARY_DB

Idempotent: the tree is skipped if TOPIC_TREE_DB already exists (override with --include-force);
summaries are resumable (skip leaves already labeled). --dry-run probes existing artifacts and
prints the plan without building or calling the LLM.
    uv run python phases/phase-5/run.py [--set-min-leaf N] [--set-coherence F] [--dry-run]
    uv run python phases/phase-5/run.py --include-summaries [--set-summary-sample N]
    uv run python phases/phase-5/run.py --include-force          # rebuild the tree
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import print_config, resolve  # noqa: E402


def _count(db: Path, query: str) -> int | None:
    """Read-only scalar; None if db/table absent."""
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row: tuple[int] = conn.execute(query).fetchone()
        finally:
            conn.close()
        return int(row[0])
    except sqlite3.Error:
        return None


def _probe() -> None:
    """Report current topic-tree + community-summary artifact state (no mutation)."""
    from _common import COMMUNITY_SUMMARY_DB, TOPIC_TREE_DB

    leaves = _count(TOPIC_TREE_DB, "SELECT count(*) FROM leaf")
    papers = _count(TOPIC_TREE_DB, "SELECT count(*) FROM paper_topic")
    summaries = _count(COMMUNITY_SUMMARY_DB, "SELECT count(*) FROM summary")
    print(f"[phase-5] topic_tree: leaves={leaves} papers={papers}")
    print(f"[phase-5] community_summaries: {summaries}")


def main() -> None:
    r = resolve(
        _HERE,
        sys.argv[1:],
        required=(
            "min_leaf",
            "coherence",
            "target_leaf",
            "max_depth",
            "max_k",
            "summaries",
            "summary_sample",
            "summary_limit",
            "force",
        ),
    )
    print_config("phase-5", r)
    _probe()

    from _common import TOPIC_TREE_DB

    c = r.config
    do_summaries = bool(c["summaries"])
    force = bool(c["force"])
    tree_exists = TOPIC_TREE_DB.exists()
    build_tree = force or not tree_exists

    plan = []
    plan.append(
        f"build topic_tree (force={force})"
        if build_tree
        else "skip topic_tree (exists)"
    )
    if do_summaries:
        plan.append(f"build community_summaries (sample={c['summary_sample']}/leaf)")
    print(f"[phase-5] plan: {', '.join(plan)}")

    if r.dry_run:
        print("[phase-5] dry-run — no build")
        return

    if build_tree:
        from topic_tree import TreeParams, run_build

        run_build(
            TreeParams(
                min_leaf=int(c["min_leaf"]),
                coherence=float(c["coherence"]),
                target_leaf=int(c["target_leaf"]),
                max_depth=int(c["max_depth"]),
                max_k=int(c["max_k"]),
            )
        )

    if do_summaries:
        from community_summary import run_summaries

        limit = int(c["summary_limit"]) or None
        run_summaries(int(c["summary_sample"]), limit)


if __name__ == "__main__":
    main()
