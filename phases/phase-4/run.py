"""Phase-4 entry point — consolidate every store into the single Postgres+pgvector DB (./data/pg).

Migrates corpus metadata (SQLite arxiv.db) + resolved citations (phase-3 output) + nomic embeddings
(.npy) + the topic tree into the one project database, then builds indexes (HNSW + tsvector +
citation) and runs a cosine alignment spot-check. Each stage is idempotent (skips an already-
populated target unless --include-force). Stages run in dependency order for `--set-only all`.

    uv run python phases/phase-4/run.py [--set-only {paper,citation,meta,emb,topic,index,check}]
                                        [--include-force] [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import print_config, resolve  # noqa: E402

from migrate_pg import ORDER, STAGES  # noqa: E402


def main() -> None:
    r = resolve(_HERE, sys.argv[1:], required=("only", "force"))
    print_config("phase-4", r)
    force = bool(r.config["force"])
    only: str = r.config["only"]  # pyright: ignore[reportAny]
    if only != "all" and only not in STAGES:
        raise SystemExit(f"--set-only must be one of {('all', *ORDER)}")
    todo = ORDER if only == "all" else [only]
    print(f"[phase-4] stages: {todo}  force={force}")
    if r.dry_run:
        print("[phase-4] dry-run: no changes")
        return
    for s in todo:
        STAGES[s](force)


if __name__ == "__main__":
    main()
