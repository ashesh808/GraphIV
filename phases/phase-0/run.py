"""Phase-0 entry point — refresh the seed metadata JSONL from the Kaggle arXiv dataset.

Downloads the Cornell-University/arxiv snapshot zip (unauthenticated), extracts the JSONL
to data/arxiv.json (atomic replace), and records the zip size for idempotency: re-running
against an unchanged snapshot is a no-op unless --include-force.
    uv run python phases/phase-0/run.py [--include-force] [--include-keep-zip] [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import print_config, resolve  # noqa: E402


def main() -> None:
    r = resolve(_HERE, sys.argv[1:], required=("url", "force", "keep_zip"))
    print_config("phase-0", r)

    from _common import ARXIV_JSON, SEED_STATE
    from seed import up_to_date

    local = f"{ARXIV_JSON.stat().st_size:,} B" if ARXIV_JSON.exists() else "MISSING"
    print(f"[phase-0] local seed: {ARXIV_JSON} ({local}); state: {SEED_STATE}")

    url = str(r.config["url"])
    if r.dry_run:
        skip, size = up_to_date(url)
        verdict = "up to date — would skip" if skip else "stale/missing — would fetch"
        print(f"[phase-0] remote zip: {size or 'unknown'} B; {verdict}")
        return

    from seed import run as seed_run

    seed_run(url, bool(r.config["force"]), bool(r.config["keep_zip"]))


if __name__ == "__main__":
    main()
