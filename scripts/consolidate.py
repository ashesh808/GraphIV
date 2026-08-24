"""
Fold metadata, citations, embeddings and the topic tree into the single Postgres store

--set-only runs one stage of the eight; the default runs them in dependency order.
"""

from __future__ import annotations

import sys

from graphiv.core.cli import print_config, resolve

STAGE = "consolidate"


def main() -> None:
    """
    Run the requested consolidation stages against the project store
    """
    r = resolve(STAGE, sys.argv[1:], required=("only", "force"))
    print_config(STAGE, r)

    from graphiv.preprocess.consolidate import ORDER, STAGES

    force = bool(r.config["force"])
    only = str(r.config["only"])
    if only != "all" and only not in STAGES:
        raise SystemExit(f"--set-only must be one of {('all', *ORDER)}")
    todo = ORDER if only == "all" else [only]
    print(f"[{STAGE}] stages: {todo}  force={force}")
    if r.dry_run:
        print(f"[{STAGE}] dry-run: no changes")
        return

    from graphiv import Preprocessor

    pre = Preprocessor.from_config(r.globals)
    for s in todo:
        pre.consolidate(stage=s, force=force)


if __name__ == "__main__":
    main()
