"""
PDF acquisition from GCS, driven by the SQLite metadata database

Batches are keyed by YYMM and fetched with aria2c, which must be installed system-wide
"""

from __future__ import annotations

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

from graphiv.download._common import ARXIV_JSON, DB_PATH, PDF_DIR, SCHEMAS_SQL


class PdfDownloader:
    """
    Manages PDF downloads from GCS against the database metadata

    Version checking makes the sync incremental and cleans up wrong-version files.
    """

    num_threads: int
    connections_per_batch: int
    pdf_dir: Path
    db_path: Path
    json_path: Path
    schemas_path: Path
    gcs_base: str
    legacy_gcs_base: str
    papers: dict[str, str]
    conn: sqlite3.Connection | None

    def __init__(self, num_threads: int = 8, connections_per_batch: int = 10) -> None:
        """
        Build a downloader with its concurrency settings

        Args:
            num_threads: concurrent YYMM batches.
            connections_per_batch: aria2c -j per batch.
        """
        self.num_threads = num_threads
        self.connections_per_batch = connections_per_batch
        self.pdf_dir = PDF_DIR
        self.db_path = DB_PATH
        self.json_path = ARXIV_JSON
        self.schemas_path = SCHEMAS_SQL
        self.gcs_base = "https://storage.googleapis.com/arxiv-dataset/arxiv/arxiv/pdf"
        self.legacy_gcs_base = "https://storage.googleapis.com/arxiv-dataset/arxiv"
        self.papers = {}
        self.conn = None

    def update_database(self) -> None:
        """
        Update SQLite from arxiv.json, inserting new rows and re-flagging version changes

        A version change resets downloaded to 0, and an unchanged row is skipped.
        """
        if not self.json_path.exists():
            print(f"JSON file not found: {self.json_path}")
            return
        if not self.schemas_path.exists():
            print(f"Schema file not found: {self.schemas_path}")
            return

        conn = sqlite3.connect(self.db_path)
        with open(self.schemas_path) as f:
            _ = conn.executescript(f.read())
        # authors added 2026-07 (schemas.sql has it for fresh DBs; ALTER covers existing)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(publication)")}
        if "authors" not in cols:
            _ = conn.execute("ALTER TABLE publication ADD COLUMN authors TEXT")

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
            versions: list[Any] = paper.get(  # pyright: ignore[reportExplicitAny]
                "versions", []
            )  # pyright: ignore[reportAny]
            if not versions:
                continue

            latest: dict[str, Any] = versions[-1]  # pyright: ignore[reportExplicitAny, reportAny]
            latest_version: str | None = latest.get("version")
            latest_version_date: str | None = latest.get("created")

            title: str = (paper.get("title", "") or "").strip()  # pyright: ignore[reportAny]
            submitter: str | None = paper.get("submitter")  # pyright: ignore[reportAny]
            abstract_raw: str = (
                paper.get("abstract", "") or ""
            ).strip()  # pyright: ignore[reportAny]
            abstract: str | None = abstract_raw or None
            doi: str | None = paper.get("doi")  # pyright: ignore[reportAny]
            journal_ref: str | None = paper.get("journal-ref")  # pyright: ignore[reportAny]
            license_: str | None = paper.get("license")  # pyright: ignore[reportAny]
            authors: str | None = paper.get("authors")  # pyright: ignore[reportAny]
            update_date: str | None = paper.get("update_date")  # pyright: ignore[reportAny]

            if paper_id in existing:
                old_version_date = existing[paper_id]
                if old_version_date == latest_version_date:
                    stats["unchanged"] += 1
                    continue
                _ = conn.execute(
                    """
                    UPDATE publication SET
                        submitter = ?, title = ?, abstract = ?, doi = ?,
                        journal_ref = ?, license = ?, authors = ?, update_date = ?,
                        latest_version = ?, latest_version_date = ?, downloaded = 0
                    WHERE id = ?
                    """,
                    (
                        submitter,
                        title,
                        abstract,
                        doi,
                        journal_ref,
                        license_,
                        authors,
                        update_date,
                        latest_version,
                        latest_version_date,
                        paper_id,
                    ),
                )
                stats["updated"] += 1
            else:
                _ = conn.execute(
                    """
                    INSERT INTO publication
                    (id, submitter, title, abstract, doi, journal_ref, license, authors,
                     update_date, latest_version, latest_version_date, downloaded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        paper_id,
                        submitter,
                        title,
                        abstract,
                        doi,
                        journal_ref,
                        license_,
                        authors,
                        update_date,
                        latest_version,
                        latest_version_date,
                    ),
                )
                stats["inserted"] += 1
                existing[paper_id] = latest_version_date

            if (stats["inserted"] + stats["updated"]) % 10000 == 0:
                conn.commit()

        conn.commit()
        print(
            f"Database update complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['unchanged']} unchanged"
        )
        self._populate_authors_and_categories(conn, papers)
        conn.close()

    def _populate_authors_and_categories(
        self,
        conn: sqlite3.Connection,
        papers: list[Any],  # pyright: ignore[reportExplicitAny]
    ) -> None:
        """
        Populate author, publication_author, and categories tables from the same JSON pass

        INSERT OR IGNORE everywhere so re-runs are safe.
        """
        author_cache: dict[tuple[str, str, str], int] = {}
        rows: list[tuple[int, str | None, str | None, str | None]] = conn.execute(
            "SELECT id, first_name, last_name, middle_name FROM author"
        ).fetchall()
        for aid, seed_fn, seed_ln, seed_mn in rows:
            author_cache[(seed_fn or "", seed_ln or "", seed_mn or "")] = aid

        author_inserts = 0
        pubauthor_inserts = 0
        cat_inserts = 0

        for paper in papers:  # pyright: ignore[reportAny]
            pid: str = paper["id"]  # pyright: ignore[reportAny]

            cat_str: str | None = paper.get("categories")  # pyright: ignore[reportAny]
            if isinstance(cat_str, str) and cat_str:
                for token in cat_str.split():
                    if "." in token:
                        cat, subcat = token.split(".", 1)
                    else:
                        cat, subcat = token, None
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO categories (publication_id, category, subcategory) "
                        "VALUES (?, ?, ?)",
                        (pid, cat, subcat),
                    )
                    if cur.rowcount > 0:
                        cat_inserts += 1

            ap: list[Any] = (
                paper.get("authors_parsed") or []
            )  # pyright: ignore[reportExplicitAny, reportAny]
            for order, triple in enumerate(ap):  # pyright: ignore[reportAny]
                if not isinstance(triple, list) or len(triple) < 2:
                    continue
                ln: str = (triple[0] or "").strip()  # pyright: ignore[reportAny]
                fn: str = (triple[1] or "").strip()  # pyright: ignore[reportAny]
                mn: str = ""
                if len(triple) > 2 and triple[2]:  # pyright: ignore[reportAny]
                    mn = str(triple[2]).strip()  # pyright: ignore[reportAny]
                if not ln and not fn:
                    continue
                key = (fn, ln, mn)
                author_id = author_cache.get(key)
                if author_id is None:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO author (first_name, last_name, middle_name) "
                        "VALUES (?, ?, ?)",
                        (fn or None, ln or None, mn or None),
                    )
                    if cur.lastrowid is not None and cur.rowcount > 0:
                        author_id = cur.lastrowid
                        author_inserts += 1
                    else:
                        row = conn.execute(
                            "SELECT id FROM author WHERE "
                            "first_name IS ? AND last_name IS ? AND middle_name IS ?",
                            (fn or None, ln or None, mn or None),
                        ).fetchone()
                        if row is None:
                            continue
                        author_id = row[0]
                    author_cache[key] = author_id

                cur = conn.execute(
                    "INSERT OR IGNORE INTO publication_author "
                    "(publication_id, author_id, author_order) VALUES (?, ?, ?)",
                    (pid, author_id, order),
                )
                if cur.rowcount > 0:
                    pubauthor_inserts += 1

            if (author_inserts + pubauthor_inserts + cat_inserts) % 50000 == 0 and (
                author_inserts + pubauthor_inserts + cat_inserts
            ) > 0:
                conn.commit()

        conn.commit()
        print(
            f"Author/category populate: {author_inserts} new authors, "
            f"{pubauthor_inserts} new publication_author links, "
            f"{cat_inserts} new category rows"
        )

    def load_database(self) -> sqlite3.Connection | None:
        """
        Refresh via update_database(), then load id->version into memory
        """
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            if self.schemas_path.exists():
                conn = sqlite3.connect(self.db_path)
                with open(self.schemas_path) as f:
                    _ = conn.executescript(f.read())
                conn.close()
            else:
                print(f"Schema file not found: {self.schemas_path}")
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
        """
        Expected path for a paper's PDF: pdf/<YYMM>/<flatname><version>.pdf
        """
        yymm = self._get_yymm(paper_id)
        if yymm is None:
            raise ValueError(f"Cannot determine YYMM for paper_id: {paper_id}")
        flatname = paper_id.replace("/", "")
        return self.pdf_dir / yymm / f"{flatname}{version}.pdf"

    def sync_downloaded_flags(self) -> None:
        """
        Scan existing PDFs on disk and mark correct ones downloaded=1
        """
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
        """
        Download missing/wrong-version PDFs, one YYMM batch at a time (aria2c)
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
                except Exception as e:  # noqa: BLE001
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
        """
        Download a single YYMM batch using aria2c
        """
        yymm_dir = self.pdf_dir / yymm
        yymm_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
            temp_path = temp_file.name
            for paper_id, version in papers:
                gcs_url = self._gcs_url(paper_id, version)
                if gcs_url is None:
                    continue
                _ = temp_file.write(f"{gcs_url}\n")
                if "/" in paper_id:
                    # the archive prefix keeps two archives sharing a YYMM from colliding
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
        """
        Check the PDF dir against the database and report mismatched files

        Only inspects .pdf files; never deletes non-PDF files or directories.

        Args:
            delete: remove wrong-version PDFs and reset the downloaded flag.

        Returns:
            {"not_in_db": [paper_id], "wrong_version": [(paper_id, version)]}.
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

    def _get_yymm(self, paper_id: str) -> str | None:
        """
        YYMM from a modern (YYMM.NNNNN) or legacy (archive/YYMMNNN) id
        """
        if "." in paper_id and paper_id[:4].isdigit():
            return paper_id.split(".")[0]
        if "/" in paper_id:
            seq = paper_id.split("/", 1)[1]
            if len(seq) >= 4 and seq[:4].isdigit():
                return seq[:4]
        return None

    def _gcs_url(self, paper_id: str, version: str) -> str | None:
        """
        GCS URL: modern arxiv/arxiv/pdf/<YYMM>/..., legacy arxiv/<archive>/pdf/....
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
        '0704.0001v2.pdf' -> ('0704.0001', 'v2'); 'hep-th9201002v1.pdf' -> ('hep-th/9201002', 'v1')
        """
        match = re.match(r"^(\d{4}\.\d+)(v\d+)\.pdf$", filename)
        if match:
            return match.group(1), match.group(2)
        match = re.match(r"^([a-zA-Z][a-zA-Z\-]*)(\d{7})(v\d+)\.pdf$", filename)
        if match:
            return f"{match.group(1)}/{match.group(2)}", match.group(3)
        return None
