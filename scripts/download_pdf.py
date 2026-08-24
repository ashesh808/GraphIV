"""
Download every missing or wrong-version PDF from GCS into the local store

--include-metadata-only stops after the JSONL to SQLite delta ingest and fetches nothing.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from graphiv.core.cli import print_config, resolve

STAGE = "pdf"


def _probe(db: Path, pdf_dir: Path) -> None:
    """
    Report metadata and download counts without mutating anything

    Args:
        db: SQLite metadata database.
        pdf_dir: root of the local PDF store.
    """
    if not db.exists():
        print(f"[{STAGE}] sqlite missing: {db}")
        return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT count(*) FROM publication").fetchone()[0]
        done = conn.execute("SELECT count(*) FROM publication WHERE downloaded = 1").fetchone()[0]
    finally:
        conn.close()
    print(f"[{STAGE}] publications={total:,} downloaded={done:,} missing={total - done:,}")
    print(f"[{STAGE}] pdf dir: {pdf_dir} ({'present' if pdf_dir.exists() else 'absent'})")


def main() -> None:
    """
    Ingest the metadata delta, then fetch the PDFs it says are missing
    """
    r = resolve(STAGE, sys.argv[1:], required=("metadata_only", "threads", "connections"))
    print_config(STAGE, r)
    _probe(r.globals.sqlite_db, r.globals.pdf_dir)

    metadata_only = bool(r.config["metadata_only"])
    if r.dry_run:
        action = "update metadata only" if metadata_only else "download missing PDFs"
        print(f"[{STAGE}] would run: {action}")
        return

    from graphiv import Downloader

    dl = Downloader.from_config(r.globals)
    dl.update_metadata()
    if not metadata_only:
        dl.download_pdfs(threads=int(r.config["threads"]), connections=int(r.config["connections"]))
    print(f"[{STAGE}] done")


if __name__ == "__main__":
    main()
