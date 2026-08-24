"""
Refresh the seed metadata JSONL from the Kaggle arXiv snapshot

Re-running against an unchanged snapshot is a no-op, keyed on the recorded remote zip size
--include-force downloads anyway.
"""

from __future__ import annotations

import sys

from graphiv.core.cli import print_config, resolve

STAGE = "seed"


def main() -> None:
    """
    Probe the local seed, then refresh it unless the snapshot is unchanged
    """
    r = resolve(STAGE, sys.argv[1:], required=("url", "force", "keep_zip"))
    print_config(STAGE, r)

    from graphiv.download._common import ARXIV_JSON, SEED_STATE
    from graphiv.download.seed import up_to_date

    local = f"{ARXIV_JSON.stat().st_size:,} B" if ARXIV_JSON.exists() else "MISSING"
    print(f"[{STAGE}] local seed: {ARXIV_JSON} ({local}); state: {SEED_STATE}")

    url = str(r.config["url"])
    if r.dry_run:
        skip, size = up_to_date(url)
        verdict = "up to date, would skip" if skip else "stale or missing, would fetch"
        print(f"[{STAGE}] remote zip: {size or 'unknown'} B; {verdict}")
        return

    from graphiv import Downloader

    Downloader.from_config(r.globals).refresh_seed(
        force=bool(r.config["force"]), keep_zip=bool(r.config["keep_zip"])
    )


if __name__ == "__main__":
    main()
