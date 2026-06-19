"""Shared helpers for phase-2 (HTML) scripts; paths from phases/global-config.json."""

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # phases/ -> _framework
from _framework import gpath, load_global  # noqa: E402

_G = load_global()
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DB_PATH = gpath(_G["sqlite"]["db"])
HTML_DIR = gpath(_G["paths"]["html_dir"])

STATUS_MISSING = -1
STATUS_OK = 1
STATUS_WARNING = 2
STATUS_ERROR = 3

_LEGACY_FILE_RE = re.compile(r"^([a-zA-Z][a-zA-Z\-]*)(\d{7})\.html$")
_MODERN_FILE_RE = re.compile(r"^(\d{4}\.\d+)\.html$")


def paper_id_to_yymm(paper_id: str) -> str | None:
    if "." in paper_id and paper_id[:4].isdigit():
        return paper_id.split(".")[0]
    if "/" in paper_id:
        seq = paper_id.split("/", 1)[1]
        if len(seq) >= 4 and seq[:4].isdigit():
            return seq[:4]
    return None


def paper_id_to_html_filename(paper_id: str) -> str:
    return paper_id.replace("/", "") + ".html"


def html_filename_to_paper_id(name: str) -> str | None:
    m = _MODERN_FILE_RE.match(name)
    if m:
        return m.group(1)
    m = _LEGACY_FILE_RE.match(name)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def paper_id_to_ar5iv_url(paper_id: str) -> str:
    return f"https://ar5iv.labs.arxiv.org/html/{paper_id}"


def html_path(paper_id: str) -> Path | None:
    yymm = paper_id_to_yymm(paper_id)
    if yymm is None:
        return None
    return HTML_DIR / yymm / paper_id_to_html_filename(paper_id)


def ensure_html_status_column(conn: sqlite3.Connection) -> None:
    """Add publication.html_status if missing. Idempotent."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(publication)")}
    if "html_status" not in cols:
        conn.execute(
            "ALTER TABLE publication ADD COLUMN html_status INTEGER DEFAULT -1"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_publication_html_status "
            "ON publication(html_status)"
        )
        conn.commit()
