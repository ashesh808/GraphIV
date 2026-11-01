"""
Fetch the LaTeXML HTML of every paper sitting at stage 1 and advance the ones that land

Two sources are tried in an order set by the paper's month, since arxiv.org only renders recent work
Work is submitted a batch at a time so a failure stops now instead of draining every pending future
"""

from __future__ import annotations

import argparse
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG

MODERN = re.compile(r"^(\d{2})(\d{2})\.\d{4,5}$")
LEGACY = re.compile(r"^[a-z-]+(?:\.[A-Za-z-]+)?/(\d{2})(\d{2})\d{3}$")
UA = "Mozilla/5.0 (X11; Linux x86_64) arxiv-kg/0.2"

# arxiv.org renders its own HTML only from this month on, before that ar5iv is the better bet
ARXIV_HTML_FROM = 202401


def yymm(arxiv_id: str) -> str | None:
    """
    The YYMM directory a paper belongs in, or None when the id is unparsable

    Args:
        arxiv_id: a modern `YYMM.NNNNN` or legacy `archive/YYMMNNN` id.

    Returns:
        The four-digit YYMM, or None.
    """
    m = MODERN.match(arxiv_id) or LEGACY.match(arxiv_id)
    return f"{m.group(1)}{m.group(2)}" if m else None


def prefer_arxiv(arxiv_id: str) -> bool:
    """
    Whether arxiv.org should be tried before ar5iv for this paper

    Args:
        arxiv_id: the paper id.

    Returns:
        True for papers from the arxiv.org HTML era.
    """
    ym = yymm(arxiv_id)
    if ym is None:
        return False
    yy, mm = int(ym[:2]), int(ym[2:])
    year = 1900 + yy if yy >= 91 else 2000 + yy
    return year * 100 + mm >= ARXIV_HTML_FROM


def looks_real(data: bytes) -> bool:
    """
    Whether a 200 carries a real LaTeXML render rather than a placeholder

    Args:
        data: the response body.

    Returns:
        True when enough LaTeXML class names are present.
    """
    return data.count(b"ltx_") >= 10


class RateLimiter:
    """
    Thread-safe token bucket shared by every worker
    """

    def __init__(self, rate: float) -> None:
        """
        Args:
            rate: permits per second, where anything at or below zero disables limiting.
        """
        self.rate = rate
        self.capacity = max(1.0, rate)
        self.tokens = self.capacity
        self.stamp = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> None:
        """
        Block until one permit is available
        """
        if self.rate <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.stamp) * self.rate)
                self.stamp = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            time.sleep(wait)


class HTMLDownloader:
    """
    The stage 1 queue and the rate-limited fetches that drain it
    """

    def __init__(self, path: str, base_url: str, fallback_url: str, rate: float) -> None:
        """
        Args:
            path: root of the local HTML store.
            base_url: arxiv.org HTML prefix.
            fallback_url: ar5iv HTML prefix.
            rate: permits per second across all workers.
        """
        self.path = Path(path)
        self.base_url = base_url.rstrip("/")
        self.fallback_url = fallback_url.rstrip("/")
        self.limiter = RateLimiter(rate)
        self.download_set: set[str] = set()

    def dest(self, arxiv_id: str) -> Path | None:
        """
        Canonical on-disk path for a paper's HTML, or None when the id is unparsable

        Args:
            arxiv_id: the paper id.

        Returns:
            The destination path.
        """
        ym = yymm(arxiv_id)
        if ym is None:
            return None
        return self.path / ym / f"{arxiv_id.replace('/', '')}.html"

    def create_queue(self, pg_dest: str) -> int:
        """
        Load every stage 1 paper into the download set

        Args:
            pg_dest: libpq connection string.

        Returns:
            How many papers are queued.
        """
        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str]] = conn.execute(
                "SELECT arxiv_id FROM papers WHERE stage = 1"
            ).fetchall()
        self.download_set = {r[0] for r in rows if yymm(r[0]) is not None}
        print(f"[stage2] queued {len(self.download_set):,} papers", flush=True)
        return len(self.download_set)

    def try_fetch(self, url: str, timeout: float) -> bytes | None:
        """
        One GET, returning the body only when it is a real render

        Args:
            url: the source to try.
            timeout: socket timeout in seconds.

        Returns:
            The body, or None for a miss, a stub or a transient failure.
        """
        self.limiter.take()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data: bytes = r.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        return data if looks_real(data) else None

    def fetch_one(self, arxiv_id: str, timeout: float = 30.0) -> bool:
        """
        Take the local file if there is one, otherwise try both sources and write the first render

        Args:
            arxiv_id: the paper id.
            timeout: socket timeout in seconds.

        Returns:
            True when a file was written.
        """
        dst = self.dest(arxiv_id)
        if dst is None:
            return False
        # a file already on disk is the answer, so a delta run never refetches one
        if dst.is_file() and dst.stat().st_size > 0:
            return True
        primary = f"{self.base_url}/{arxiv_id}"
        secondary = f"{self.fallback_url}/{arxiv_id}"
        order = (primary, secondary) if prefer_arxiv(arxiv_id) else (secondary, primary)
        for url in order:
            data = self.try_fetch(url, timeout)
            if data is None:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".html.part")
            _ = tmp.write_bytes(data)
            os.replace(tmp, dst)
            return True
        return False

    def download(self, pg_dest: str, batch: int, parallel: int) -> int:
        """
        Drain the stage 1 queue in batches, advancing whatever lands on disk

        Args:
            pg_dest: libpq connection string.
            batch: papers per commit.
            parallel: worker threads.

        Returns:
            How many papers reached stage 2.
        """
        if not self.download_set:
            _ = self.create_queue(pg_dest)
        queue = sorted(self.download_set)
        done = 0
        with psycopg.connect(pg_dest, autocommit=True) as conn:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                for i in range(0, len(queue), batch):
                    chunk = queue[i : i + batch]
                    got = pool.map(self.fetch_one, chunk)
                    ok = [a for a, landed in zip(chunk, got, strict=True) if landed]
                    if ok:
                        _ = conn.execute(
                            "UPDATE papers SET stage = 2 WHERE arxiv_id = ANY(%s) AND stage = 1",
                            (ok,),
                        )
                    done += len(ok)
                    print(
                        f"[stage2] {i + len(chunk):,}/{len(queue):,} tried, {done:,} landed",
                        flush=True,
                    )
        return done


def main() -> None:
    """
    Read the config, then drain the stage 1 queue
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    dl = HTMLDownloader(
        path=str(cfg["dataset"]["HTML_PATH"]),
        base_url=str(cfg["source"]["HTML_BASE_URL"]),
        fallback_url=str(cfg["source"]["HTML_FALLBACK_URL"]),
        rate=float(cfg["download"]["HTML_RATE"]),
    )
    _ = dl.download(
        str(cfg["database"]["PG_DEST"]),
        batch=int(cfg["download"]["HTML_BATCH"]),
        parallel=int(cfg["download"]["HTML_N_PARALLEL"]),
    )


if __name__ == "__main__":
    main()
