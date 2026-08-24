"""
Acquire LaTeXML HTML renders for papers that do not have one yet

--include-migrate instead folds a pre-existing ar5iv dump into the canonical layout, once.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from graphiv.core.cli import print_config, resolve

STAGE = "html"


def _probe(db: Path) -> None:
    """
    Report the html_status breakdown without mutating anything

    Args:
        db: SQLite metadata database.
    """
    if not db.exists():
        print(f"[{STAGE}] sqlite missing: {db}")
        return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.execute("SELECT html_status, count(*) FROM publication GROUP BY html_status")
        counts = {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()
    print(f"[{STAGE}] html_status counts: {counts}")


def main() -> None:
    """
    Run either the one-shot dump migration or the rate-limited download sweep
    """
    r = resolve(STAGE, sys.argv[1:], required=("migrate", "rate", "threads", "limit"))
    print_config(STAGE, r)
    _probe(r.globals.sqlite_db)

    from graphiv import Downloader

    dl = Downloader.from_config(r.globals)
    if bool(r.config["migrate"]):
        if r.dry_run:
            print(f"[{STAGE}] would run: one-shot HTML dump migration")
            return
        dl.migrate_html()
        return

    if r.dry_run:
        print(f"[{STAGE}] would run: disk resweep plus download of html_status=-1 candidates")
        return
    dl.download_html(
        rate=float(r.config["rate"]),
        threads=int(r.config["threads"]),
        limit=int(r.config["limit"]) or None,
    )


if __name__ == "__main__":
    main()
