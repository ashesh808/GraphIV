#!/usr/bin/env python3
"""
PDF Downloader for arXiv Knowledge Graph

Downloads and manages PDF files from GCS storage based on database metadata.
Supports version checking, incremental updates, and cleanup of incorrect files.

Usage:
    python download.py                    # Check and download missing PDFs
"""

# reference /home/kuroma/Documents/projects/nlp/arxiv_kg/data_processing/scripts/download_pdf.py

import json
import os
import re
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class Downloader:
    """PDF Downloader for arXiv Knowledge Graph.

    Manages PDF downloads from GCS storage based on database metadata.
    """

    def __init__(self, base_path=None, num_threads=8, connections_per_batch=10):
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

        self.internal_db = None  # sqlite db - loaded manually when needed

    def update_database(self):
        """Update database from arxiv.json with version checking.

        Loads JSON, compares with existing database, updates only when
        version changes, setting downloaded=0 for updated papers.
        """
        # Check if JSON file exists
        if not self.json_path.exists():
            print(f"JSON file not found: {self.json_path}")
            return

        # Load schema first (CRITICAL: load before any DB operations)
        schema_path = self.base_path / "metadata" / "schemas.sql"
        if not schema_path.exists():
            print(f"Schema file not found: {schema_path}")
            return

        # Connect to database
        conn = sqlite3.connect(self.db_path)

        # Apply schema
        with open(schema_path) as f:
            conn.executescript(f.read())

        # Load existing papers for comparison
        existing = {}
        cursor = conn.execute("SELECT id, latest_version_date FROM publication")
        for row in cursor:
            existing[row[0]] = row[1]

        # Read JSONL file
        papers = []
        with open(self.json_path) as f:
            for line in f:
                if line.strip():
                    papers.append(json.loads(line))

        # Process papers
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        for paper in papers:
            paper_id = paper["id"]
            versions = paper.get("versions", [])
            if not versions:
                continue

            latest = versions[-1]
            latest_version = latest.get("version")
            latest_version_date = latest.get("created")

            title = paper.get("title", "").strip()
            submitter = paper.get("submitter")
            abstract = paper.get("abstract", "").strip() or None
            doi = paper.get("doi")
            journal_ref = paper.get("journal-ref")
            license_ = paper.get("license")
            update_date = paper.get("update_date")

            # Check if paper exists and if version changed
            if paper_id in existing:
                old_version_date = existing[paper_id]
                if old_version_date == latest_version_date:
                    stats["unchanged"] += 1
                    continue

                # Version changed - update and mark as not downloaded
                conn.execute(
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
                # New paper - insert
                conn.execute(
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

            # Commit periodically
            if (stats["inserted"] + stats["updated"]) % 10000 == 0:
                conn.commit()

        # Final commit
        conn.commit()
        conn.close()

        print(
            f"Database update complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['unchanged']} unchanged"
        )

    def load_database(self):
        """Load database contents into memory.

        Calls update_database() first to ensure data is fresh, then loads
        papers into self.papers dict and stores connection in self.conn.
        """
        # Ensure database exists
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            schema_path = self.base_path / "metadata" / "schemas.sql"
            if schema_path.exists():
                conn = sqlite3.connect(self.db_path)
                with open(schema_path) as f:
                    conn.executescript(f.read())
                conn.close()
            else:
                print(f"Schema file not found: {schema_path}")
                return None

        self.update_database()

        conn = sqlite3.connect(self.db_path)

        self.papers = {}
        cursor = conn.execute("SELECT id, latest_version FROM publication")
        for row in cursor:
            paper_id, latest_version = row
            self.papers[paper_id] = latest_version

        self.conn = conn

        return conn

    def _pdf_path(self, paper_id: str, version: str) -> Path:
        """Return the expected path for a paper's PDF: pdf/<YYMM>/<flatname><version>.pdf"""
        yymm = self._get_yymm(paper_id)
        flatname = paper_id.replace("/", "")
        return self.pdf_dir / yymm / f"{flatname}{version}.pdf"

    def sync_downloaded_flags(self):
        """Scan existing PDFs on disk and mark correct ones as downloaded=1 in DB."""
        if not self.pdf_dir.exists():
            return

        marked = 0
        for pdf_file in self.pdf_dir.rglob("*.pdf"):
            parsed = self._parse_pdf_filename(pdf_file.name)
            if not parsed:
                continue
            paper_id, file_version = parsed
            if paper_id in self.papers and file_version == self.papers[paper_id]:
                self.conn.execute(
                    "UPDATE publication SET downloaded = 1 WHERE id = ? AND downloaded = 0",
                    (paper_id,),
                )
                marked += 1
        if marked:
            self.conn.commit()
            print(f"Marked {marked} existing PDFs as already downloaded")

    def download(self):
        """Download PDFs from GCS storage with YYMM-based batching.

        Downloads missing and wrong-version papers one YYMM batch at a time
        using aria2c.
        """
        self.load_database()
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.sync_downloaded_flags()

        # Build download list: all papers with downloaded=0
        papers_to_download = []
        cursor = self.conn.execute(
            "SELECT id, latest_version FROM publication WHERE downloaded = 0"
        )
        for paper_id, version in cursor:
            yymm = self._get_yymm(paper_id)
            if yymm:
                papers_to_download.append((paper_id, version, yymm))

        print(f"Total papers to download: {len(papers_to_download)}")

        if not papers_to_download:
            print("Nothing to download")
            return

        yymm_groups = defaultdict(list)
        for paper_id, version, yymm in papers_to_download:
            yymm_groups[yymm].append((paper_id, version))

        print(f"Batches: {len(yymm_groups)} YYMM groups, {self.num_threads} concurrent")

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {}
            for yymm, papers in sorted(yymm_groups.items()):
                future = executor.submit(self._download_batch, yymm, papers)
                futures[future] = (yymm, papers)

            for future in as_completed(futures):
                yymm, papers = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Batch {yymm} failed: {e}")

        # After all batches, sync what actually landed on disk
        print("\nSyncing download state...")
        self.sync_downloaded_flags()
        downloaded = self.conn.execute(
            "SELECT count(*) FROM publication WHERE downloaded = 1"
        ).fetchone()[0]
        print(f"Total downloaded: {downloaded}")

    def _download_batch(self, yymm, papers):
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
                temp_file.write(f"{gcs_url}\n")
                if "/" in paper_id:
                    # Force archive-prefixed local filename to avoid
                    # collisions across archives sharing the same YYMM/seq.
                    local_name = paper_id.replace("/", "") + f"{version}.pdf"
                    temp_file.write(f"  out={local_name}\n")

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
            subprocess.run(aria2c_cmd, check=True)
            print(f"Batch {yymm} complete ({len(papers)} papers)")
        except subprocess.CalledProcessError as e:
            print(f"Batch {yymm} had errors: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def clean(self, delete=False):
        """Check PDF directory against database and report mismatched files.

        Only inspects .pdf files. Never deletes non-PDF files or directories.

        Args:
            delete: If True, remove wrong-version PDFs and reset downloaded flag

        Returns:
            dict with two lists:
                - report["not_in_db"]: list of paper_ids not in database
                - report["wrong_version"]: list of (paper_id, file_version) tuples
        """
        report = {"not_in_db": [], "wrong_version": []}

        if not self.pdf_dir.exists():
            return report

        for pdf_file in self.pdf_dir.rglob("*.pdf"):
            if not pdf_file.is_file():
                continue

            parsed = self._parse_pdf_filename(pdf_file.name)
            if not parsed:
                continue

            paper_id, file_version = parsed

            if paper_id not in self.papers:
                report["not_in_db"].append(paper_id)
                continue

            expected_version = self.papers[paper_id]
            if file_version != expected_version:
                report["wrong_version"].append((paper_id, file_version))
                if delete:
                    pdf_file.unlink()
                    self.conn.execute(
                        "UPDATE publication SET downloaded = 0 WHERE id = ?",
                        (paper_id,),
                    )

        if delete:
            self.conn.commit()

        return report

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
    parser.add_argument(
        "-t", "--threads", type=int, default=8,
        help="number of concurrent YYMM batches (default: 8)",
    )
    parser.add_argument(
        "-j", "--connections", type=int, default=10,
        help="aria2c connections per batch (default: 10)",
    )
    args = parser.parse_args()

    downloader = Downloader(num_threads=args.threads, connections_per_batch=args.connections)
    downloader.download()
    print("done")
