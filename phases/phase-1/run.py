"""Phase-1 entry point — download arXiv PDFs from GCS (preprocessing).

Ingests arxiv.json metadata into SQLite, syncs the downloaded flag from disk, then downloads
missing/wrong-version PDFs in YYMM batches via aria2c. Non-destructive: it only adds files and
version-checks metadata; it never deletes. --dry-run does a read-only DB/disk probe only.
    uv run python phases/phase-1/run.py [--include-metadata-only]
                                        [--set-threads N] [--set-connections N] [--dry-run]
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import gpath, print_config, resolve  # noqa: E402


def _probe(db: Path, pdf_dir: Path) -> None:
    """Read-only counts of metadata + download state (no mutation)."""
    if not db.exists():
        print(f"[phase-1] sqlite missing: {db}")
        return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT count(*) FROM publication").fetchone()[0]
        done = conn.execute(
            "SELECT count(*) FROM publication WHERE downloaded = 1"
        ).fetchone()[0]
    finally:
        conn.close()
    print(
        f"[phase-1] publications={total:,} downloaded={done:,} missing={total - done:,}"
    )
    print(
        f"[phase-1] pdf dir: {pdf_dir} ({'present' if pdf_dir.exists() else 'absent'})"
    )


def main() -> None:
    r = resolve(
        _HERE, sys.argv[1:], required=("metadata_only", "threads", "connections")
    )
    print_config("phase-1", r)
    db = gpath(r.globals["sqlite"]["db"])
    pdf_dir = gpath(r.globals["paths"]["pdf_dir"])
    _probe(db, pdf_dir)

    metadata_only = bool(r.config["metadata_only"])
    if r.dry_run:
        action = (
            "update_database (metadata only)"
            if metadata_only
            else "download missing PDFs"
        )
        print(f"[phase-1] would run: {action}")
        return

    from download import Downloader

    # base_path = repo-root data/ (db, json, schema, pdf all hang off it), not phases/phase-1/data
    base_path = db.parent.parent
    dl = Downloader(
        base_path=base_path,
        num_threads=int(r.config["threads"]),
        connections_per_batch=int(r.config["connections"]),
    )
    dl.update_database()  # delta ingest: only new/changed rows are written
    if not metadata_only:
        dl.download()  # syncs downloaded flags from disk, then fetches downloaded=0 via aria2c
    print("[phase-1] done")


if __name__ == "__main__":
    main()
