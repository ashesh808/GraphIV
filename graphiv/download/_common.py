"""
Config bridge and the id-to-path helpers the download modules share

Constants are read once when the subpackage is first imported
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

DATA_DIR: Path = _C.data_dir
ARXIV_JSON: Path = _C.arxiv_json
SEED_STATE: Path = ARXIV_JSON.parent / "metadata" / "seed_state.json"
DB_PATH: Path = _C.sqlite_db
SCHEMAS_SQL: Path = _C.sqlite_schemas
PDF_DIR: Path = _C.pdf_dir
HTML_DIR: Path = _C.html_dir
KAGGLE_URL: str = _C.kaggle_url
HTML_MIGRATE_SRC: Path = Path(_C.html_migrate_src)

STATUS_MISSING = -1
STATUS_OK = 1
STATUS_WARNING = 2
STATUS_ERROR = 3

# past this month arXiv's own render is current, and before it ar5iv is
ARXIV_HTML_CUTOFF_YYYYMM = 202401

_LEGACY_FILE_RE = re.compile(r"^([a-zA-Z][a-zA-Z\-]*)(\d{7})\.html$")
_MODERN_FILE_RE = re.compile(r"^(\d{4}\.\d+)\.html$")


def paper_id_to_yymm(paper_id: str) -> str | None:
    """
    YYMM directory name from a modern or legacy id; None if unparsable
    """
    if "." in paper_id and paper_id[:4].isdigit():
        return paper_id.split(".")[0]
    if "/" in paper_id:
        seq = paper_id.split("/", 1)[1]
        if len(seq) >= 4 and seq[:4].isdigit():
            return seq[:4]
    return None


def paper_id_to_html_filename(paper_id: str) -> str:
    """
    Flat on-disk filename (legacy slashes removed)
    """
    return paper_id.replace("/", "") + ".html"


def html_filename_to_paper_id(name: str) -> str | None:
    """
    Inverse of paper_id_to_html_filename; None for foreign filenames
    """
    m = _MODERN_FILE_RE.match(name)
    if m:
        return m.group(1)
    m = _LEGACY_FILE_RE.match(name)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def paper_id_to_ar5iv_url(paper_id: str) -> str:
    """
    ar5iv LaTeXML render URL
    """
    return f"https://ar5iv.labs.arxiv.org/html/{paper_id}"


def paper_id_to_arxiv_html_url(paper_id: str) -> str:
    """
    arxiv.org native LaTeXML render URL
    """
    return f"https://arxiv.org/html/{paper_id}"


def yymm_to_yyyymm(yymm: str) -> int:
    """
    YYMM -> sortable YYYYMM, pivoting 91-99 to 19xx (arXiv epoch)
    """
    yy, mm = int(yymm[:2]), int(yymm[2:4])
    year = 1900 + yy if yy >= 91 else 2000 + yy
    return year * 100 + mm


def prefer_arxiv_html(paper_id: str) -> bool:
    """
    True if the paper's date is at/after the arXiv-HTML cutoff
    """
    yymm = paper_id_to_yymm(paper_id)
    return yymm is not None and yymm_to_yyyymm(yymm) >= ARXIV_HTML_CUTOFF_YYYYMM


def html_path(paper_id: str) -> Path | None:
    """
    Canonical on-disk HTML path for a paper, or None if the id is unparsable
    """
    yymm = paper_id_to_yymm(paper_id)
    if yymm is None:
        return None
    return HTML_DIR / yymm / paper_id_to_html_filename(paper_id)


def ensure_html_status_column(conn: sqlite3.Connection) -> None:
    """
    Add publication.html_status if missing

    Idempotent.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(publication)")}
    if "html_status" not in cols:
        _ = conn.execute("ALTER TABLE publication ADD COLUMN html_status INTEGER DEFAULT -1")
        _ = conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_publication_html_status " "ON publication(html_status)"
        )
        conn.commit()
