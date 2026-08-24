"""
HTML acquisition from arxiv.org and ar5iv, plus the one-shot dump migration

Papers past the cutoff prefer arXiv's own LaTeXML render and older ones prefer ar5iv
The sweep re-checks disk first, so files that arrived out of band are not fetched twice
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from graphiv.download._common import (
    DB_PATH,
    HTML_DIR,
    HTML_MIGRATE_SRC,
    STATUS_ERROR,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_WARNING,
    ensure_html_status_column,
    html_filename_to_paper_id,
    html_path,
    paper_id_to_ar5iv_url,
    paper_id_to_arxiv_html_url,
    paper_id_to_yymm,
    prefer_arxiv_html,
)

# Browser-like UA: arxiv.org rejects some scripted agents; ar5iv accepts anything
_UA = "Mozilla/5.0 (X11; Linux x86_64) arxiv-kg/0.2"


def _looks_real(data: bytes) -> bool:
    """
    LaTeXML output carries many ltx_ CSS classes, and an ar5iv failure stub has none
    """
    return data.count(b"ltx_") >= 10


def _try_fetch(url: str, limiter: RateLimiter, timeout: float) -> tuple[bytes | None, str]:
    """
    One GET

    (data, 'ok') for real HTML; (None, '404'|'stub'|'err') otherwise.
    """
    limiter.acquire()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # pyright: ignore[reportAny]
            data: bytes = resp.read()  # pyright: ignore[reportAny]
    except urllib.error.HTTPError as e:
        return None, "404" if e.code == 404 else "err"
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "err"
    return (data, "ok") if _looks_real(data) else (None, "stub")


class RateLimiter:
    """
    Token bucket: at most `rate` permits issued per second across threads
    """

    rate: float
    capacity: float
    tokens: float
    last: float
    lock: threading.Lock

    def __init__(self, rate: float) -> None:
        """
        Build a token bucket at the given rate

        Args:
            rate: permits per second; <= 0 disables limiting.
        """
        self.rate = float(rate)
        self.capacity = max(1.0, self.rate)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """
        Block until a permit is available
        """
        if self.rate <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            time.sleep(wait)


def disk_resweep(conn: sqlite3.Connection) -> int:
    """
    For html_status=-1 rows whose files happen to exist, flip to STATUS_OK
    """
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
    batch = 5000
    for i in range(0, len(found), batch):
        chunk = found[i : i + batch]
        placeholders = ",".join("?" * len(chunk))
        _ = cur.execute(
            f"UPDATE publication SET html_status = ? WHERE html_status = ? "
            f"AND id IN ({placeholders})",
            (STATUS_OK, STATUS_MISSING, *chunk),
        )
        updated += cur.rowcount
        conn.commit()
    return updated


def download_one(
    paper_id: str, limiter: RateLimiter, timeout: float = 30.0
) -> tuple[str, int | None, str | None]:
    """
    Fetch real HTML, trying arxiv.org + ar5iv in date-determined order with the other as fallback

    (paper_id, status, msg), where None means a stub or transient failure to retry next run.
    """
    dst = html_path(paper_id)
    if dst is None:
        return paper_id, None, "no yymm"
    arxiv = paper_id_to_arxiv_html_url(paper_id)
    ar5iv = paper_id_to_ar5iv_url(paper_id)
    sources = [arxiv, ar5iv] if prefer_arxiv_html(paper_id) else [ar5iv, arxiv]

    outcomes: list[str] = []
    for url in sources:
        data, outcome = _try_fetch(url, limiter, timeout)
        outcomes.append(outcome)
        if outcome == "ok" and data is not None:
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".html.part")
            _ = tmp.write_bytes(data)
            os.replace(tmp, dst)
            return paper_id, STATUS_OK, None

    if all(o == "404" for o in outcomes):
        return paper_id, STATUS_ERROR, "404 (both sources)"
    return paper_id, None, "+".join(outcomes)


def run(
    rate: float = 5.0,
    threads: int = 8,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """
    Download missing HTML; dry_run lists candidates without writing
    """
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
    permanent = 0
    err = 0
    err_sample: dict[str, int] = {}
    batch = 500

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        _ = conn.executemany("UPDATE publication SET html_status = ? WHERE id = ?", pending)
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
            if len(pending) >= batch:
                flush()
            if i % 200 == 0:
                top = sorted(err_sample.items(), key=lambda x: -x[1])[:3]
                top_str = ", ".join(f"{k}={v}" for k, v in top)
                print(
                    f"  progress {i}/{len(candidates)}  ok={ok} "
                    f"permanent={permanent} err={err}"
                    + (f"  top_errors=[{top_str}]" if top_str else "")
                )
    flush()
    print(f"Done. ok={ok} permanent(404/503)={permanent} transient_err={err}")
    if err_sample:
        for msg, count in sorted(err_sample.items(), key=lambda x: -x[1]):
            print(f"  {count:>6}x  {msg}")
    conn.close()


def migrate() -> None:
    """
    Move a pre-existing ar5iv dump into the canonical layout and set publication.html_status

    A lower status wins on collision, so a clean render is never replaced by a warning.

    Rerunnable.
    """
    sources = [
        ("no-problem", STATUS_OK),
        ("warning", STATUS_WARNING),
        ("error", STATUS_ERROR),
    ]
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_html_status_column(conn)

    paper_status: dict[str, int] = {}
    moved = {1: 0, 2: 0, 3: 0}
    skipped = 0
    unparsed = 0

    for subdir, status in sources:
        root = HTML_MIGRATE_SRC / subdir
        if not root.exists():
            continue
        print(f"Scanning {root} ...")
        for yymm_dir in sorted(root.iterdir()):
            if not yymm_dir.is_dir():
                continue
            dst_yymm = HTML_DIR / yymm_dir.name
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
    batch = 5000
    updated = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        _ = cursor.executemany(
            "UPDATE publication SET html_status = ? WHERE id = ?",
            [(status, pid) for pid, status in chunk],
        )
        updated += cursor.rowcount if cursor.rowcount > 0 else 0
        conn.commit()
        if (i // batch) % 10 == 0:
            print(f"  ... {i + len(chunk)}/{len(rows)}")
    print(f"DB updates applied for ~{updated} rows.")

    counts = dict(
        conn.execute("SELECT html_status, count(*) FROM publication GROUP BY html_status")
    )
    print(f"html_status distribution: {counts}")
    conn.close()
