#!/usr/bin/env python3
"""HTML downloader for arXiv (ar5iv).

Sweeps publication rows whose html_status = -1, re-checks on disk in case
files arrived out-of-band, then downloads the rest from
https://ar5iv.labs.arxiv.org/html/<arxiv_id>. Newly downloaded files get
html_status = 1 (ar5iv classifies pages on its own; the migration script
preserves the original 1/2/3 split for files we already had).

phase_1/download.py never reads or writes html_status — that's owned here.

Usage:
    python -m phase_2.download [--rate 5.0] [--threads 8] [--limit N] [--dry-run]
"""

import argparse
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._common import (
    DB_PATH,
    HTML_DIR,
    STATUS_ERROR,
    STATUS_MISSING,
    STATUS_OK,
    ensure_html_status_column,
    html_filename_to_paper_id,
    html_path,
    paper_id_to_ar5iv_url,
    paper_id_to_yymm,
)


class RateLimiter:
    """Token bucket: at most `rate` permits issued per second across threads."""

    rate: float
    capacity: float
    tokens: float
    last: float
    lock: threading.Lock

    def __init__(self, rate: float):
        self.rate = float(rate)
        self.capacity = max(1.0, self.rate)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        if self.rate <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity, self.tokens + (now - self.last) * self.rate
                )
                self.last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            time.sleep(wait)


def disk_resweep(conn: sqlite3.Connection) -> int:
    """For html_status=-1 rows whose files happen to exist, flip to STATUS_OK."""
    if not HTML_DIR.exists():
        return 0
    found: list[str] = []
    for yymm_dir in HTML_DIR.iterdir():
        if not yymm_dir.is_dir():
            continue
        for entry in os.scandir(yymm_dir):
            if not entry.is_file() or not entry.name.endswith(".html"):
                continue
            pid = html_filename_to_paper_id(entry.name)
            if pid:
                found.append(pid)
    if not found:
        return 0

    cur = conn.cursor()
    updated = 0
    BATCH = 5000
    for i in range(0, len(found), BATCH):
        chunk = found[i : i + BATCH]
        placeholders = ",".join("?" * len(chunk))
        _ = cur.execute(
            f"UPDATE publication SET html_status = ? WHERE html_status = ? AND id IN ({placeholders})",
            (STATUS_OK, STATUS_MISSING, *chunk),
        )
        updated += cur.rowcount
        conn.commit()
    return updated


def download_one(
    paper_id: str, limiter: RateLimiter, timeout: float = 30.0
) -> tuple[str, int | None, str | None]:
    """Returns (paper_id, status_or_None, error_msg_or_None).

    status: STATUS_OK on 200; None on 404 (leave at -1); None on other errors too.
    """
    dst = html_path(paper_id)
    if dst is None:
        return paper_id, None, "no yymm"
    url = paper_id_to_ar5iv_url(paper_id)
    limiter.acquire()
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-kg/0.1"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # pyright: ignore[reportAny]
                data: bytes = resp.read()  # pyright: ignore[reportAny]
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".html.part")
            tmp.write_bytes(data)  # pyright: ignore[reportUnusedCallResult]
            os.replace(tmp, dst)
            return paper_id, STATUS_OK, None
        except urllib.error.HTTPError as e:
            # 404 and 503 are permanent "not available" from ar5iv — mark and skip
            if e.code in (404, 503):
                return paper_id, STATUS_ERROR, f"HTTP {e.code}"
            if attempt == 2:
                return paper_id, None, f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 2:
                return paper_id, None, f"{type(e).__name__}: {e}"
        time.sleep(1.0)
    return paper_id, None, "unreachable"


def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv HTML downloader (ar5iv)")
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--rate", type=float, default=5.0,
        help="max downloads per second across all threads (default: 5)",
    )
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--threads", type=int, default=8,
        help="worker thread count (default: 8)",
    )
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--limit", type=int, default=None,
        help="cap number of papers attempted this run",
    )
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--dry-run", action="store_true",
        help="list candidates without downloading",
    )
    args = parser.parse_args()
    rate: float = args.rate  # pyright: ignore[reportAny]
    threads: int = args.threads  # pyright: ignore[reportAny]
    limit: int | None = args.limit  # pyright: ignore[reportAny]
    dry_run: bool = args.dry_run  # pyright: ignore[reportAny]

    conn = sqlite3.connect(DB_PATH)
    ensure_html_status_column(conn)

    print("Disk resweep ...")
    flipped = disk_resweep(conn)
    print(f"  flipped {flipped} rows from -1 -> 1 based on existing files")

    rows: list[tuple[str]] = conn.execute(
        "SELECT id FROM publication WHERE html_status = ?",
        (STATUS_MISSING,),
    ).fetchall()
    candidates = [r[0] for r in rows if paper_id_to_yymm(r[0]) is not None]
    if limit:
        candidates = candidates[:limit]
    print(f"Candidates to download: {len(candidates)}")

    if dry_run:
        for pid in candidates[:20]:
            print(f"  {pid} -> {paper_id_to_ar5iv_url(pid)}")
        if len(candidates) > 20:
            print(f"  ... ({len(candidates) - 20} more)")
        conn.close()
        return

    if not candidates:
        conn.close()
        return

    limiter = RateLimiter(rate)
    pending: list[tuple[int, str]] = []
    ok = 0
    permanent = 0  # 404 / 503 — written as STATUS_ERROR, won't be retried
    err = 0
    err_sample: dict[str, int] = {}
    BATCH = 500

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        _ = conn.executemany(
            "UPDATE publication SET html_status = ? WHERE id = ?", pending
        )
        conn.commit()
        pending = []

    with ThreadPoolExecutor(max_workers=threads) as ex:
        futures = [ex.submit(download_one, pid, limiter) for pid in candidates]
        for i, fut in enumerate(as_completed(futures), 1):
            pid, status, err_msg = fut.result()
            if status == STATUS_OK:
                pending.append((STATUS_OK, pid))
                ok += 1
            elif status == STATUS_ERROR:
                pending.append((STATUS_ERROR, pid))
                permanent += 1
            else:
                err += 1
                if err_msg:
                    err_sample[err_msg] = err_sample.get(err_msg, 0) + 1
            if len(pending) >= BATCH:
                flush()
            if i % 200 == 0:
                top = sorted(err_sample.items(), key=lambda x: -x[1])[:3]
                top_str = ", ".join(f"{k}={v}" for k, v in top)
                print(
                    f"  progress {i}/{len(candidates)}  ok={ok} permanent={permanent} err={err}"
                    + (f"  top_errors=[{top_str}]" if top_str else "")
                )
    flush()
    print(f"Done. ok={ok} permanent(404/503)={permanent} transient_err={err}")
    if err_sample:
        top = sorted(err_sample.items(), key=lambda x: -x[1])
        print("Transient error breakdown:")
        for msg, count in top:
            print(f"  {count:>6}x  {msg}")
    conn.close()


if __name__ == "__main__":
    main()
