"""Phase-2 entry point — acquire arXiv HTML from ar5iv (preprocessing).

Default: download HTML for publications with html_status = -1 (after a disk resweep). Non-
destructive: only writes new files and flips status flags forward. --include-migrate runs the
one-shot dump migration instead. --dry-run lists candidates / intent without writing.
    uv run python phases/phase-2/run.py [--include-migrate]
                                        [--set-rate R] [--set-threads N] [--set-limit N] [--dry-run]
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import gpath, print_config, resolve  # noqa: E402


def _probe(db: Path) -> None:
    """Read-only html_status breakdown (no mutation)."""
    if not db.exists():
        print(f"[phase-2] sqlite missing: {db}")
        return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT html_status, count(*) FROM publication GROUP BY html_status"
        )
        counts = {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()
    print(f"[phase-2] html_status counts: {counts}")


def main() -> None:
    r = resolve(_HERE, sys.argv[1:], required=("migrate", "rate", "threads", "limit"))
    print_config("phase-2", r)
    _probe(gpath(r.globals["sqlite"]["db"]))

    if bool(r.config["migrate"]):
        if r.dry_run:
            print("[phase-2] would run: one-shot HTML dump migration (migrate_html)")
            return
        from migrate_html import main as migrate

        migrate()
        return

    # Download path: dry-run stays read-only here; only a real run resweeps + writes.
    limit = int(r.config["limit"]) or None
    if r.dry_run:
        print(
            "[phase-2] would run: disk resweep + download of html_status=-1 candidates"
        )
        return
    from download import run as download

    download(float(r.config["rate"]), int(r.config["threads"]), limit, False)


if __name__ == "__main__":
    main()
