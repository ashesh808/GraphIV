#!/usr/bin/env python3
"""PDF Downloader for arXiv Knowledge Graph

Downloads and manages PDF files from GCS storage based on database metadata.
Supports version checking, incremental updates, and cleanup of incorrect files.

Usage:
    python -m phase_1.download                    # Check and download missing PDFs
"""

# reference /home/kuroma/Documents/projects/nlp/arxiv_kg/data_processing/scripts/download_pdf.py

import json
import os
import re
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


class Downloader:
    """PDF Downloader for arXiv Knowledge Graph.

    Manages PDF downloads from GCS storage based on database metadata.
    """

    base_path: Path
    num_threads: int
    connections_per_batch: int
    pdf_dir: Path
    db_path: Path
    json_path: Path
    gcs_base: str
    legacy_gcs_base: str
    papers: dict[str, str]
    conn: sqlite3.Connection | None

    def __init__(
        self,
        base_path: Path | None = None,
        num_threads: int = 8,
        connections_per_batch: int = 10,
    ):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data"

        self.base_path = base_path
        self.num_threads = num_threads
        self.connections_per_batch = connections_per_batch
        self.pdf_dir = self.base_path / "pdf"
        self.db_path = self.base_path / "metadata" / "arxiv.db"
        self.json_path = self.base_path / "arxiv.json"
        self.gcs_base = "https://storage.googleapis.com/arxiv-dataset/arxiv/arxiv/pdf"
        self.legacy_gcs_base = "https://storage.googleapis.com/arxiv-dataset/arxiv"
        self.papers = {}
        self.conn = None

    def update_database(self) -> None:
        """Update database from arxiv.json with version checking.

        Loads JSON, compares with existing database, updates only when
        version changes, setting downloaded=0 for updated papers.
        """
        if not self.json_path.exists():
            print(f"JSON file not found: {self.json_path}")
            return

        schema_path = self.base_path / "metadata" / "schemas.sql"
        if not schema_path.exists():
            print(f"Schema file not found: {schema_path}")
            return

        conn = sqlite3.connect(self.db_path)

        with open(schema_path) as f:
            _ = conn.executescript(f.read())

        existing: dict[str, str | None] = {}
        rows: list[tuple[str, str | None]] = conn.execute(
            "SELECT id, latest_version_date FROM publication"
        ).fetchall()
        for row in rows:
            existing[row[0]] = row[1]

        papers: list[Any] = []  # pyright: ignore[reportExplicitAny]
        with open(self.json_path) as f:
            for line in f:
                if line.strip():
                    papers.append(json.loads(line))

        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        for paper in papers:  # pyright: ignore[reportAny]
            paper_id: str = paper["id"]  # pyright: ignore[reportAny]
            versions: list[Any] = paper.get("versions", [])  # pyright: ignore[reportExplicitAny, reportAny]
            if not versions:
                continue

            latest: dict[str, Any] = versions[-1]  # pyright: ignore[reportExplicitAny, reportAny]
            latest_version: str | None = latest.get("version")
            latest_version_date: str | None = latest.get("created")

            title: str = (paper.get("title", "") or "").strip()  # pyright: ignore[reportAny]
            submitter: str | None = paper.get("submitter")  # pyright: ignore[reportAny]
            abstract_raw: str = (paper.get("abstract", "") or "").strip()  # pyright: ignore[reportAny]
            abstract: str | None = abstract_raw or None
            doi: str | None = paper.get("doi")  # pyright: ignore[reportAny]
            journal_ref: str | None = paper.get("journal-ref")  # pyright: ignore[reportAny]
            license_: str | None = paper.get("license")  # pyright: ignore[reportAny]
            update_date: str | None = paper.get("update_date")  # pyright: ignore[reportAny]

            if paper_id in existing:
                old_version_date = existing[paper_id]
                if old_version_date == latest_version_date:
                    stats["unchanged"] += 1
                    continue

                _ = conn.execute(
                    """
                    UPDATE publication SET
                        submitter = ?,
                        title = ?,
                        abstract = ?,
                        doi = ?,
                        journal_ref = ?,
                        license = ?,
                        update_date = ?,
                        latest_version = ?,
                        latest_version_date = ?,
                        downloaded = 0
                    WHERE id = ?
                """,
                    (submitter, title, abstract, doi, journal_ref, license_,
                     update_date, latest_version, latest_version_date, paper_id),
                )
                stats["updated"] += 1
            else:
                _ = conn.execute(
                    """
                    INSERT INTO publication
                    (id, submitter, title, abstract, doi, journal_ref, license,
                     update_date, latest_version, latest_version_date, downloaded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                    (paper_id, submitter, title, abstract, doi, journal_ref,
                     license_, update_date, latest_version, latest_version_date),
                )
                stats["inserted"] += 1
                existing[paper_id] = latest_version_date

            if (stats["inserted"] + stats["updated"]) % 10000 == 0:
                conn.commit()

        conn.commit()
        conn.close()

        print(
            f"Database update complete: {stats['inserted']} inserted, {stats['updated']} updated, {stats['unchanged']} unchanged"
        )

    def load_database(self) -> sqlite3.Connection | None:
        """Load database contents into memory.

        Calls update_database() first to ensure data is fresh, then loads
        papers into self.papers dict and stores connection in self.conn.
        """
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            schema_path = self.base_path / "metadata" / "schemas.sql"
            if schema_path.exists():
                conn = sqlite3.connect(self.db_path)
                with open(schema_path) as f:
                    _ = conn.executescript(f.read())
                conn.close()
            else:
                print(f"Schema file not found: {schema_path}")
                return None

        self.update_database()

        conn = sqlite3.connect(self.db_path)

        self.papers = {}
        rows: list[tuple[str, str]] = conn.execute(
            "SELECT id, latest_version FROM publication"
        ).fetchall()
        for row in rows:
            paper_id, latest_version = row
            self.papers[paper_id] = latest_version

        self.conn = conn
        return conn

    def _pdf_path(self, paper_id: str, version: str) -> Path:
        """Return the expected path for a paper's PDF: pdf/<YYMM>/<flatname><version>.pdf"""
        yymm = self._get_yymm(paper_id)
        if yymm is None:
            raise ValueError(f"Cannot determine YYMM for paper_id: {paper_id}")
        flatname = paper_id.replace("/", "")
        return self.pdf_dir / yymm / f"{flatname}{version}.pdf"

    def sync_downloaded_flags(self) -> None:
        """Scan existing PDFs on disk and mark correct ones as downloaded=1 in DB."""
        assert self.conn is not None
        if not self.pdf_dir.exists():
            return

        marked = 0
        for pdf_file in self.pdf_dir.rglob("*.pdf"):
            parsed = self._parse_pdf_filename(pdf_file.name)
            if not parsed:
                continue
            paper_id, file_version = parsed
            if paper_id in self.papers and file_version == self.papers[paper_id]:
                _ = self.conn.execute(
                    "UPDATE publication SET downloaded = 1 WHERE id = ? AND downloaded = 0",
                    (paper_id,),
                )
                marked += 1
        if marked:
            self.conn.commit()
            print(f"Marked {marked} existing PDFs as already downloaded")

    def download(self) -> None:
        """Download PDFs from GCS storage with YYMM-based batching.

        Downloads missing and wrong-version papers one YYMM batch at a time
        using aria2c.
        """
        _ = self.load_database()
        if self.conn is None:
            return
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.sync_downloaded_flags()

        papers_to_download: list[tuple[str, str, str]] = []
        rows: list[tuple[str, str]] = self.conn.execute(
            "SELECT id, latest_version FROM publication WHERE downloaded = 0"
        ).fetchall()
        for paper_id, version in rows:
            yymm = self._get_yymm(paper_id)
            if yymm:
                papers_to_download.append((paper_id, version, yymm))

        print(f"Total papers to download: {len(papers_to_download)}")

        if not papers_to_download:
            print("Nothing to download")
            return

        yymm_groups: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        for paper_id, version, yymm in papers_to_download:
            yymm_groups[yymm].append((paper_id, version))

        print(f"Batches: {len(yymm_groups)} YYMM groups, {self.num_threads} concurrent")

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures: dict[Future[None], tuple[str, list[tuple[str, str]]]] = {}
            for yymm, batch in sorted(yymm_groups.items()):
                future = executor.submit(self._download_batch, yymm, batch)
                futures[future] = (yymm, batch)

            for future in as_completed(futures):
                yymm, batch = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Batch {yymm} failed: {e}")

        print("\nSyncing download state...")
        self.sync_downloaded_flags()
        count_row = self.conn.execute(  # pyright: ignore[reportAny]
            "SELECT count(*) FROM publication WHERE downloaded = 1"
        ).fetchone()
        assert count_row is not None
        downloaded: int = count_row[0]  # pyright: ignore[reportAny]
        print(f"Total downloaded: {downloaded}")

    def _download_batch(self, yymm: str, papers: list[tuple[str, str]]) -> None:
        """Download a single YYMM batch using aria2c."""
        yymm_dir = self.pdf_dir / yymm
        yymm_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_path = temp_file.name
            for paper_id, version in papers:
                gcs_url = self._gcs_url(paper_id, version)
                if gcs_url is None:
                    continue
                _ = temp_file.write(f"{gcs_url}\n")
                if "/" in paper_id:
                    # Force archive-prefixed local filename to avoid
                    # collisions across archives sharing the same YYMM/seq.
                    local_name = paper_id.replace("/", "") + f"{version}.pdf"
                    _ = temp_file.write(f"  out={local_name}\n")

        aria2c_cmd = [
            "aria2c",
            "-i",
            temp_path,
            "-j",
            str(self.connections_per_batch),
            "-d",
            str(yymm_dir),
            "--continue=true",
            "--max-tries=3",
            "--summary-interval=30",
        ]

        try:
            _ = subprocess.run(aria2c_cmd, check=True)
            print(f"Batch {yymm} complete ({len(papers)} papers)")
        except subprocess.CalledProcessError as e:
            print(f"Batch {yymm} had errors: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def clean(self, delete: bool = False) -> dict[str, list[str] | list[tuple[str, str]]]:
        """Check PDF directory against database and report mismatched files.

        Only inspects .pdf files. Never deletes non-PDF files or directories.

        Args:
            delete: If True, remove wrong-version PDFs and reset downloaded flag

        Returns:
            dict with two lists:
                - report["not_in_db"]: list of paper_ids not in database
                - report["wrong_version"]: list of (paper_id, file_version) tuples
        """
        not_in_db: list[str] = []
        wrong_version: list[tuple[str, str]] = []

        if not self.pdf_dir.exists():
            return {"not_in_db": not_in_db, "wrong_version": wrong_version}

        for pdf_file in self.pdf_dir.rglob("*.pdf"):
            if not pdf_file.is_file():
                continue

            parsed = self._parse_pdf_filename(pdf_file.name)
            if not parsed:
                continue

            paper_id, file_version = parsed

            if paper_id not in self.papers:
                not_in_db.append(paper_id)
                continue

            expected_version = self.papers[paper_id]
            if file_version != expected_version:
                wrong_version.append((paper_id, file_version))
                if delete:
                    assert self.conn is not None
                    pdf_file.unlink()
                    _ = self.conn.execute(
                        "UPDATE publication SET downloaded = 0 WHERE id = ?",
                        (paper_id,),
                    )

        if delete:
            assert self.conn is not None
            self.conn.commit()

        return {"not_in_db": not_in_db, "wrong_version": wrong_version}

    # helper functions go here, start name with an undercore

    def _get_yymm(self, paper_id: str) -> str | None:
        """Extract YYMM from paper ID. Handles modern (YYMM.NNNNN) and legacy
        (archive/YYMMNNN) IDs."""
        if "." in paper_id and paper_id[:4].isdigit():
            return paper_id.split(".")[0]
        if "/" in paper_id:
            seq = paper_id.split("/", 1)[1]
            if len(seq) >= 4 and seq[:4].isdigit():
                return seq[:4]
        return None

    def _gcs_url(self, paper_id: str, version: str) -> str | None:
        """Build the GCS download URL for a paper.

        Modern: arxiv/arxiv/pdf/<YYMM>/<id><ver>.pdf       (self.gcs_base)
        Legacy: arxiv/<archive>/pdf/<YYMM>/<seq><ver>.pdf  (self.legacy_gcs_base)
        """
        if "/" in paper_id:
            archive, seq = paper_id.split("/", 1)
            yymm = seq[:4]
            return f"{self.legacy_gcs_base}/{archive}/pdf/{yymm}/{seq}{version}.pdf"
        yymm = self._get_yymm(paper_id)
        if yymm is None:
            return None
        return f"{self.gcs_base}/{yymm}/{paper_id}{version}.pdf"

    def _parse_pdf_filename(self, filename: str) -> tuple[str, str] | None:
        """
        Parse PDF filename to extract paper_id and version.
        Modern: '0704.0001v2.pdf' -> ('0704.0001', 'v2')
        Legacy: 'hep-th9201002v1.pdf' -> ('hep-th/9201002', 'v1')
        """
        match = re.match(r"^(\d{4}\.\d+)(v\d+)\.pdf$", filename)
        if match:
            return match.group(1), match.group(2)
        match = re.match(r"^([a-zA-Z][a-zA-Z\-]*)(\d{7})(v\d+)\.pdf$", filename)
        if match:
            return f"{match.group(1)}/{match.group(2)}", match.group(3)
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="arXiv PDF downloader")
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "-t", "--threads", type=int, default=8,
        help="number of concurrent YYMM batches (default: 8)",
    )
    parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "-j", "--connections", type=int, default=10,
        help="aria2c connections per batch (default: 10)",
    )
    args = parser.parse_args()
    threads: int = args.threads  # pyright: ignore[reportAny]
    connections: int = args.connections  # pyright: ignore[reportAny]

    downloader = Downloader(num_threads=threads, connections_per_batch=connections)
    downloader.download()
    print("done")
