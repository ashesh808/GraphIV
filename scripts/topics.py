"""
Build the density-aware topic tree, and optionally the per-leaf community summaries

The tree is only rebuilt when it is absent or --include-force is given, since it is expensive.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from graphiv.core.cli import print_config, resolve

STAGE = "topics"


def _count(db: Path, query: str) -> int | None:
    """
    Read one SQLite scalar read-only

    Args:
        db: database file.
        query: a scalar-returning SELECT.

    Returns:
        The count, or None when the file or table is absent.
    """
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


def main() -> None:
    """
    Report the current artifacts, then build whichever ones the config asks for
    """
    r = resolve(
        STAGE,
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
    print_config(STAGE, r)

    tree_db = r.globals.topic_tree_db
    print(
        f"[{STAGE}] topic_tree: leaves={_count(tree_db, 'SELECT count(*) FROM leaf')} "
        f"papers={_count(tree_db, 'SELECT count(*) FROM paper_topic')}"
    )
    summaries_db = r.globals.community_summary_db
    print(f"[{STAGE}] community_summaries: {_count(summaries_db, 'SELECT count(*) FROM summary')}")

    c = r.config
    do_summaries = bool(c["summaries"])
    force = bool(c["force"])
    build_tree = force or not tree_db.exists()

    plan = [f"build topic_tree (force={force})" if build_tree else "skip topic_tree (exists)"]
    if do_summaries:
        plan.append(f"build community_summaries (sample={c['summary_sample']}/leaf)")
    print(f"[{STAGE}] plan: {', '.join(plan)}")

    if r.dry_run:
        print(f"[{STAGE}] dry-run, no build")
        return

    from graphiv import Preprocessor

    pre = Preprocessor.from_config(r.globals)
    if build_tree:
        pre.build_topic_tree(
            min_leaf=int(c["min_leaf"]),
            coherence=float(c["coherence"]),
            target_leaf=int(c["target_leaf"]),
            max_depth=int(c["max_depth"]),
            max_k=int(c["max_k"]),
        )
    if do_summaries:
        pre.build_summaries(sample=int(c["summary_sample"]), limit=int(c["summary_limit"]) or None)


if __name__ == "__main__":
    main()
