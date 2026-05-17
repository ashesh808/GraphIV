#!/usr/bin/env python3
"""One-shot migration: move ar5iv HTMLs into the canonical vault layout and
populate publication.html_status.

Source: /mnt/Vault-Storage/temp/ar5iv/{no-problem,warning,error}/<yymm>/<file>.html
Dest:   data/html/<yymm>/<file>.html  (symlink -> /mnt/Vault-Storage/arxiv-html)

Status mapping: no-problem=1, warning=2, error=3. On collision the better
(lower-numbered) status wins.

Rerunnable: a destination already at a better status is left alone; worse-
status duplicates at the source are deleted.
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    DB_PATH,
    HTML_DIR,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_WARNING,
    ensure_html_status_column,
    html_filename_to_paper_id,
)

SRC_ROOT = Path("/mnt/Vault-Storage/temp/ar5iv")
SOURCES = [
    ("no-problem", STATUS_OK),
    ("warning", STATUS_WARNING),
    ("error", STATUS_ERROR),
]


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_html_status_column(conn)

    paper_status: dict[str, int] = {}
    moved = {1: 0, 2: 0, 3: 0}
    skipped = 0
    unparsed = 0
    no_paper_id = 0

    for subdir, status in SOURCES:
        root = SRC_ROOT / subdir
        if not root.exists():
            continue
        print(f"Scanning {root} ...")
        for yymm_dir in sorted(root.iterdir()):
            if not yymm_dir.is_dir():
                continue
            yymm = yymm_dir.name
            dst_yymm = HTML_DIR / yymm
            dst_yymm.mkdir(parents=True, exist_ok=True)
            for entry in os.scandir(yymm_dir):
                if not entry.is_file() or not entry.name.endswith(".html"):
                    continue
                pid = html_filename_to_paper_id(entry.name)
                if pid is None:
                    unparsed += 1
                    continue
                dst = dst_yymm / entry.name
                src = Path(entry.path)
                if dst.exists():
                    existing = paper_status.get(pid)
                    if existing is not None and existing <= status:
                        src.unlink()
                        skipped += 1
                        continue
                    dst.unlink()
                os.replace(src, dst)
                paper_status[pid] = status
                moved[status] += 1

    print(
        f"Moved: ok={moved[1]} warn={moved[2]} err={moved[3]} "
        f"skipped={skipped} unparsed_filenames={unparsed}"
    )

    print("Updating DB ...")
    rows = list(paper_status.items())
    cursor = conn.cursor()
    BATCH = 5000
    updated = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        cursor.executemany(
            "UPDATE publication SET html_status = ? WHERE id = ?",
            [(status, pid) for pid, status in chunk],
        )
        updated += cursor.rowcount if cursor.rowcount > 0 else 0
        conn.commit()
        if (i // BATCH) % 10 == 0:
            print(f"  ... {i + len(chunk)}/{len(rows)}")
    no_paper_id = len(rows) - updated if updated >= 0 else 0
    print(f"DB updates applied for ~{updated} rows; {no_paper_id} ids not in DB.")

    counts = dict(
        conn.execute(
            "SELECT html_status, count(*) FROM publication GROUP BY html_status"
        )
    )
    print(f"html_status distribution: {counts}")
    conn.close()


if __name__ == "__main__":
    main()
