"""
The Downloader: wiring only, one idempotent operation per method

Every method works over the shared SQLite metadata database and the file stores
"""

from __future__ import annotations

from dataclasses import dataclass

from graphiv.core.config import Config
from graphiv.download import html, seed
from graphiv.download.pdf import PdfDownloader


@dataclass
class Downloader:
    """
    metadata -> files

    Methods map 1:1 onto the old phase entry points.
    """

    cfg: Config

    @classmethod
    def from_config(cls, cfg: Config | None = None) -> Downloader:
        """
        Build from config.toml (loaded fresh when omitted)
        """
        return cls(cfg=cfg or Config.load())

    def refresh_seed(self, force: bool = False, keep_zip: bool = False) -> None:
        """
        Refresh data/arxiv.json from Kaggle (idempotent by remote zip size)
        """
        seed.run(self.cfg.kaggle_url, force=force, keep_zip=keep_zip)

    def update_metadata(self) -> None:
        """
        JSONL -> SQLite metadata (version-checked; authors/categories too)
        """
        PdfDownloader().update_database()

    def download_pdfs(self, threads: int = 8, connections: int = 10) -> None:
        """
        Download missing/wrong-version PDFs from GCS (aria2c, YYMM batches)
        """
        PdfDownloader(num_threads=threads, connections_per_batch=connections).download()

    def download_html(self, rate: float = 5.0, threads: int = 8, limit: int | None = None) -> None:
        """
        Download missing LaTeXML HTML (arxiv.org/ar5iv, rate-limited)
        """
        html.run(rate=rate, threads=threads, limit=limit)

    def migrate_html(self) -> None:
        """
        One-shot: fold a pre-existing ar5iv dump into the canonical layout
        """
        html.migrate()
