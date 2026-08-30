"""
Fetch the PDF of every paper sitting at stage 0 and advance the ones that land

Each aria2c batch carries a per-entry destination, so one batch spans months and stays saturated
A paper only advances when its file is on disk, which makes a partial batch safe to re-run
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

import psycopg

MODERN = re.compile(r"^(\d{2})(\d{2})\.\d{4,5}$")
LEGACY = re.compile(r"^[a-z-]+(?:\.[A-Za-z-]+)?/(\d{2})(\d{2})\d{3}$")


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


def flat_name(arxiv_id: str, version: str) -> str:
    """
    On-disk filename, with the archive prefix folded in so two archives cannot collide

    Args:
        arxiv_id: the paper id.
        version: the `vN` string.

    Returns:
        The bare filename.
    """
    return f"{arxiv_id.replace('/', '')}{version}.pdf"


class PDFDownloader:
    """
    The stage 0 queue and the aria2c batches that drain it
    """

    def __init__(self, path: str, base_url: str, legacy_base_url: str) -> None:
        """
        Args:
            path: root of the local PDF store.
            base_url: GCS prefix for modern ids.
            legacy_base_url: GCS prefix for `archive/NNNNNNN` ids.
        """
        self.path = Path(path)
        self.base_url = base_url.rstrip("/")
        self.legacy_base_url = legacy_base_url.rstrip("/")
        self.download_set: set[tuple[str, str]] = set()

    def url_for(self, arxiv_id: str, version: str) -> str | None:
        """
        GCS URL for one paper, or None when the id has no YYMM

        Args:
            arxiv_id: the paper id.
            version: the `vN` string.

        Returns:
            A fully qualified URL, or None.
        """
        ym = yymm(arxiv_id)
        if ym is None:
            return None
        if "/" in arxiv_id:
            archive, seq = arxiv_id.split("/", 1)
            return f"{self.legacy_base_url}/{archive}/pdf/{ym}/{seq}{version}.pdf"
        return f"{self.base_url}/{ym}/{arxiv_id}{version}.pdf"

    def create_queue(self, pg_dest: str) -> int:
        """
        Load every stage 0 paper into the download set

        Args:
            pg_dest: libpq connection string.

        Returns:
            How many papers are queued.
        """
        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str, str]] = conn.execute(
                "SELECT arxiv_id, COALESCE(latest_version, 'v1') FROM papers WHERE stage = 0"
            ).fetchall()
        self.download_set = {(a, v) for a, v in rows if yymm(a) is not None}
        print(f"[stage1] queued {len(self.download_set):,} papers", flush=True)
        return len(self.download_set)

    def landed(self, arxiv_id: str, version: str) -> bool:
        """
        Whether this paper's file is on disk and non-empty

        Args:
            arxiv_id: the paper id.
            version: the `vN` string.

        Returns:
            True when the file exists with content.
        """
        ym = yymm(arxiv_id)
        if ym is None:
            return False
        f = self.path / ym / flat_name(arxiv_id, version)
        return f.is_file() and f.stat().st_size > 0

    def fetch_batch(self, batch: list[tuple[str, str]], parallel: int) -> None:
        """
        Run one aria2c invocation over a batch, writing each file to its own month

        Args:
            batch: the papers to fetch.
            parallel: concurrent connections for aria2c.
        """
        lines: list[str] = []
        for arxiv_id, version in batch:
            url = self.url_for(arxiv_id, version)
            ym = yymm(arxiv_id)
            if url is None or ym is None:
                continue
            # already on disk, so a delta run does not ask GCS for it again
            if self.landed(arxiv_id, version):
                continue
            (self.path / ym).mkdir(parents=True, exist_ok=True)
            lines.append(url)
            lines.append(f"  dir={self.path / ym}")
            lines.append(f"  out={flat_name(arxiv_id, version)}")
        if not lines:
            return

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            _ = fh.write("\n".join(lines) + "\n")
            listing = fh.name
        try:
            _ = subprocess.run(
                # a 404 is an expected outcome here, so a non-zero exit is not an error
                [
                    "aria2c",
                    "-i",
                    listing,
                    "-j",
                    str(parallel),
                    "--continue=true",
                    "--max-tries=2",
                    "--quiet=true",
                ],
                check=False,
            )
        finally:
            Path(listing).unlink(missing_ok=True)

    def download(self, pg_dest: str, batch: int, parallel: int) -> int:
        """
        Drain the stage 0 queue in batches, advancing whatever lands on disk

        Args:
            pg_dest: libpq connection string.
            batch: papers per aria2c invocation.
            parallel: concurrent connections for aria2c.

        Returns:
            How many papers reached stage 1.
        """
        if not self.download_set:
            _ = self.create_queue(pg_dest)
        queue = sorted(self.download_set)
        done = 0
        with psycopg.connect(pg_dest, autocommit=True) as conn:
            for i in range(0, len(queue), batch):
                chunk = queue[i : i + batch]
                self.fetch_batch(chunk, parallel)
                ok = [a for a, v in chunk if self.landed(a, v)]
                if ok:
                    _ = conn.execute(
                        "UPDATE papers SET stage = 1 WHERE arxiv_id = ANY(%s) AND stage = 0",
                        (ok,),
                    )
                done += len(ok)
                print(
                    f"[stage1] {i + len(chunk):,}/{len(queue):,} tried, {done:,} landed",
                    flush=True,
                )
        return done


def main() -> None:
    """
    Read the config, then drain the stage 0 queue
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = tomllib.loads(
        Path(str(args.config_path)).read_text(encoding="utf-8")
    )  # pyright: ignore[reportAny]
    dl = PDFDownloader(
        path=str(cfg["dataset"]["PDF_PATH"]),
        base_url=str(cfg["source"]["PDF_BASE_URL"]),
        legacy_base_url=str(cfg["source"]["PDF_LEGACY_BASE_URL"]),
    )
    _ = dl.download(
        str(cfg["database"]["PG_DEST"]),
        batch=int(cfg["download"]["PDF_BATCH"]),
        parallel=int(cfg["download"]["PDF_N_PARALLEL"]),
    )


if __name__ == "__main__":
    main()
