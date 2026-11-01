"""
Refresh the source metadata JSON and insert every arXiv id the papers table is missing

New rows land at stage 0 carrying metadata only, which is the queue the download stages drain
The JSON is streamed a line at a time as holding all of it costs about 16GB
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import psycopg

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG

MODERN = re.compile(r"^(\d{2})(\d{2})\.\d{4,5}$")
LEGACY = re.compile(r"^[a-z-]+(?:\.[A-Za-z-]+)?/(\d{2})(\d{2})\d{3}$")

COLUMNS = (
    "arxiv_id",
    "title",
    "abstract",
    "date",
    "primary_category",
    "authors",
    "surnames",
    "latest_version",
    "doi",
    "journal_ref",
)


def yymm(arxiv_id: str) -> str | None:
    """
    The YYMM directory a paper's files live in, or None when the id is unparsable

    Args:
        arxiv_id: a modern or legacy arXiv id.

    Returns:
        The four-digit YYMM.
    """
    m = MODERN.match(arxiv_id) or LEGACY.match(arxiv_id)
    return f"{m.group(1)}{m.group(2)}" if m else None


def stale_files(arxiv_id: str, old_version: str, pdf_dir: Path, html_dir: Path) -> list[Path]:
    """
    The files a superseded version leaves behind

    The HTML carries no version in its name, so a new version invalidates it outright.

    Args:
        arxiv_id: the paper id.
        old_version: the version the table currently holds.
        pdf_dir: root of the PDF store.
        html_dir: root of the HTML store.

    Returns:
        Existing paths that should go.
    """
    ym = yymm(arxiv_id)
    if ym is None:
        return []
    flat = arxiv_id.replace("/", "")
    out = [pdf_dir / ym / f"{flat}{old_version}.pdf", html_dir / ym / f"{flat}.html"]
    return [p for p in out if p.is_file()]


def _rfc_date(raw: str) -> date | None:
    """
    Parse an arXiv version timestamp like 'Mon, 2 Apr 2007 19:18:42 GMT'

    Args:
        raw: the `created` field of one version entry.

    Returns:
        The calendar date, or None when the field is unparsable.
    """
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError):
        return None


def _row(rec: dict[str, Any]) -> tuple[object, ...]:  # pyright: ignore[reportExplicitAny]
    """
    Turn one source record into a papers row in COLUMNS order

    Args:
        rec: one decoded line of the source JSON.

    Returns:
        A tuple ready for COPY, with None wherever the source is silent.

    A record carrying no versions is given v1, since latest_version is NOT NULL.
    """
    versions: list[dict[str, str]] = rec.get("versions") or []
    parsed: list[list[str]] = rec.get("authors_parsed") or []
    categories: str = rec.get("categories") or ""
    return (
        rec["id"],
        (rec.get("title") or "").strip() or None,
        (rec.get("abstract") or "").strip() or None,
        _rfc_date(versions[0]["created"]) if versions else None,
        categories.split()[0] if categories.split() else None,
        rec.get("authors"),
        [p[0] for p in parsed if p and p[0]],
        versions[-1].get("version") if versions else "v1",
        rec.get("doi"),
        rec.get("journal-ref"),
    )


class SourceFetcher:
    """
    The source JSON on disk and the papers rows it implies
    """

    def __init__(self, source_path: str, source_url: str) -> None:
        """
        Args:
            source_path: where the JSONL lives, and where `.temp` is written beside it.
            source_url: the Kaggle download endpoint, which serves a zip.
        """
        self.path = Path(source_path)
        self.url = source_url
        self.temp = self.path.with_name(self.path.name + ".temp")

    def fetch_url(self) -> Path:
        """
        Download the snapshot and extract its JSON member to the temp path

        The endpoint serves a zip, so the member is extracted rather than streamed straight out.

        Returns:
            The temp path holding the freshly downloaded JSONL.
        """
        archive = self.path.with_name(self.path.name + ".temp.zip")
        print(f"[stage0] downloading {self.url}", flush=True)
        _ = subprocess.run(
            ["curl", "-fsSL", "--retry", "3", "-C", "-", "-o", str(archive), self.url],
            check=True,
        )
        with zipfile.ZipFile(archive) as z:
            member = next(n for n in z.namelist() if n.endswith(".json"))
            print(f"[stage0] extracting {member}", flush=True)
            with z.open(member) as src, self.temp.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        archive.unlink()
        return self.temp

    def newest(self, path: Path) -> date | None:
        """
        The most recent first-submission date in a JSONL, or None when it is empty

        Args:
            path: a source JSONL to scan.

        Returns:
            The maximum submission date over every record.
        """
        best: date | None = None
        for rec in self.records(path):
            versions: list[dict[str, str]] = rec.get("versions") or []
            when = _rfc_date(versions[0]["created"]) if versions else None
            if when is not None and (best is None or when > best):
                best = when
        return best

    def fetch_and_replace(self) -> bool:
        """
        Download a snapshot and keep it only when it carries newer papers than the current one

        Returns:
            True when the file on disk was replaced.
        """
        fresh = self.fetch_url()
        if not self.path.exists():
            _ = fresh.replace(self.path)
            print("[stage0] no local snapshot, took the download", flush=True)
            return True

        new_max, old_max = self.newest(fresh), self.newest(self.path)
        print(f"[stage0] newest paper: local {old_max}, remote {new_max}", flush=True)
        if new_max is not None and (old_max is None or new_max > old_max):
            _ = fresh.replace(self.path)
            print("[stage0] replaced the local snapshot", flush=True)
            return True
        fresh.unlink()
        print("[stage0] local snapshot is current, discarded the download", flush=True)
        return False

    def records(
        self, path: Path | None = None
    ) -> Iterator[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
        """
        Decode a source JSONL one line at a time

        Args:
            path: the file to read, defaulting to the configured source path.

        Yields:
            One decoded record per non-blank line.
        """
        with (path or self.path).open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)  # pyright: ignore[reportAny]

    def update_db(
        self,
        pg_dest: str,
        pdf_dir: Path,
        html_dir: Path,
        fetch: bool = True,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """
        Bring papers level with the source, resetting any paper whose version moved

        A new version invalidates the whole derived chain for that paper, so its PDF, its HTML,
        its citation rows and its vectors all go, and it re-enters the pipeline at stage 0.

        Args:
            pg_dest: libpq connection string for the destination.
            pdf_dir: root of the PDF store.
            html_dir: root of the HTML store.
            fetch: refresh the snapshot first, which a re-run can skip.
            dry_run: report what would change and touch nothing.

        Returns:
            (rows inserted, papers reset for a new version).
        """
        if fetch and not dry_run:
            _ = self.fetch_and_replace()

        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str, str | None]] = conn.execute(
                "SELECT arxiv_id, latest_version FROM papers"
            ).fetchall()
            have = {a: v for a, v in rows}
            print(f"[stage0] papers holds {len(have):,} ids, scanning the source", flush=True)

            fresh: list[tuple[object, ...]] = []
            bumped: list[tuple[str, str]] = []
            seen: set[str] = set()
            for rec in self.records():
                aid = str(rec["id"])  # pyright: ignore[reportAny]
                # the source repeats a handful of ids, and the first record of each one wins
                if aid in seen:
                    continue
                seen.add(aid)
                row = _row(rec)
                version = str(row[7] or "v1")
                if aid not in have:
                    fresh.append(row)
                elif (have[aid] or "v1") != version:
                    bumped.append((aid, have[aid] or "v1"))
                    fresh.append(row)

            ids = [a for a, _ in bumped]
            doomed = [f for a, v in bumped for f in stale_files(a, v, pdf_dir, html_dir)]
            edges = 0
            if ids:
                row = conn.execute(
                    "SELECT count(*) FROM citations WHERE source_id = ANY(%s)", (ids,)
                ).fetchone()
                edges = int(row[0]) if row else 0

            print(f"[stage0] {len(fresh):,} new rows", flush=True)
            print(f"[stage0] {len(bumped):,} papers moved to a new version", flush=True)
            print(f"[stage0] {len(doomed):,} superseded files to remove", flush=True)
            print(f"[stage0] {edges:,} citations to drop from those papers", flush=True)
            for f in doomed[:5]:
                print(f"[stage0]     {f}", flush=True)
            if dry_run:
                print("[stage0] dry run, nothing written", flush=True)
                return 0, 0

            """
            A new version invalidates everything derived from the old text, so the outgoing
            citations go with the row.
            Citations pointing at this paper survive, since its arxiv_id still names the same work.
            """
            if ids:
                _ = conn.execute("DELETE FROM citations WHERE source_id = ANY(%s)", (ids,))
                _ = conn.execute("DELETE FROM papers WHERE arxiv_id = ANY(%s)", (ids,))

            cols = ", ".join(COLUMNS)
            with conn.cursor().copy(f"COPY papers ({cols}) FROM STDIN") as cp:
                for i, row in enumerate(fresh, 1):
                    cp.write_row(row)
                    if i % 500_000 == 0:
                        print(f"[stage0]   +{i:,}", flush=True)
            conn.commit()

        # files go only once the rows are committed, so a rollback cannot strand the store
        for f in doomed:
            f.unlink(missing_ok=True)
        print(f"[stage0] inserted {len(fresh):,} rows, reset {len(bumped):,} papers", flush=True)
        return len(fresh), len(bumped)


def main() -> None:
    """
    Read the config, then bring the papers table level with the source JSON
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    _ = ap.add_argument("--no-fetch", action="store_true", help="use the JSON already on disk")
    _ = ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    fetcher = SourceFetcher(
        source_path=str(cfg["source"]["SOURCE_PATH"]),
        source_url=str(cfg["source"]["SOURCE_URL"]),
    )
    _ = fetcher.update_db(
        str(cfg["database"]["PG_DEST"]),
        pdf_dir=Path(str(cfg["dataset"]["PDF_PATH"])),
        html_dir=Path(str(cfg["dataset"]["HTML_PATH"])),
        fetch=not bool(args.no_fetch),  # pyright: ignore[reportAny]
        dry_run=bool(args.dry_run),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
