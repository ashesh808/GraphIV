"""
The citation labeling server: the queue, the Postgres lookups and the rendered PDF pages

Labels append to the same JSONL the keyboard tool writes, so doomscroll --to-pg reads either
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, LiteralString, cast
from urllib.parse import parse_qs, urlparse

import psycopg
import pymupdf

from graphiv.core.config import Config
from graphiv.download.fetch import local_pdf

from .._common import INTENTS, LABELS_DIR
from ..pdfview import locate, open_pdf, render
from .page import html

QUEUE: Path = LABELS_DIR / "gold_items.jsonl"
LABELS: Path = LABELS_DIR / "gold_labels.jsonl"

AXES: list[dict[str, object]] = [
    {"name": "intent", "keys": "123456", "options": list(INTENTS)},
]

DETAIL_SQL: LiteralString = """
SELECT p.arxiv_id, cm.title, cm.authors, cm.year, cm.primary_category, cm.abstract,
       q.arxiv_id, dm.title, dm.authors, dm.year, dm.primary_category,
       COALESCE(c.section, ''), c.sentence, c.intent
FROM citation c
JOIN paper p ON p.id = c.citing_id
LEFT JOIN paper_meta cm ON cm.arxiv_id = p.arxiv_id
LEFT JOIN paper q ON q.id = c.cited_id
LEFT JOIN paper_meta dm ON dm.arxiv_id = q.arxiv_id
WHERE c.citing_id = %s AND c.ordinal = %s
"""


@dataclass(frozen=True)
class Paper:
    """
    One paper as the side panel shows it
    """

    arxiv_id: str
    title: str
    authors: str
    year: int | None
    category: str


@dataclass
class Item:
    """
    One citation occurrence, both endpoints resolved, located inside the citing PDF
    """

    citing_id: int
    ordinal: int
    section: str
    sentence: str
    abstract: str
    citing: Paper
    cited: Paper
    pages: int
    page: int
    needles: list[str]
    hint_intent: str


class Store:
    """
    The queue, the labels written so far, and the PDF of the item on screen
    """

    def __init__(self, queue: Path, out: Path, labeler: str) -> None:
        self.pairs: list[tuple[int, int]] = []
        with open(queue, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = cast(dict[str, int], json.loads(line))
                    self.pairs.append((d["citing_id"], d["ordinal"]))
        self.out: Path = out
        self.labeler: str = labeler
        self.done: dict[str, dict[str, object]] = {}
        if out.exists():
            with open(out, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = cast(dict[str, object], json.loads(line))
                        self.done[str(row["key"])] = row
        self.dsn: str = Config.load().pg_dsn
        self._doc: pymupdf.Document | None = None
        self._doc_key: tuple[int, int] | None = None
        self._rects: list[tuple[float, float, float, float]] = []
        self._page: int = 0

    @staticmethod
    def key(citing_id: int, ordinal: int) -> str:
        """
        The row key the keyboard tool also writes
        """
        return f"{citing_id}:{ordinal}"

    def next_pair(self) -> tuple[int, int] | None:
        """
        The first pair with no label yet
        """
        for pair in self.pairs:
            if self.key(*pair) not in self.done:
                return pair
        return None

    def item(self, citing_id: int, ordinal: int) -> Item | None:
        """
        Everything the panel needs, including where the sentence sits in the PDF
        """
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(DETAIL_SQL, (citing_id, ordinal)).fetchone()
        if row is None:
            return None
        r = cast(tuple[Any, ...], row)  # pyright: ignore[reportExplicitAny]
        sentence = str(r[12] or "")
        doc = self.document(citing_id, ordinal, str(r[0]))
        page, needles, pages = 0, [], 0
        self._rects = []
        if doc is not None:
            pages = doc.page_count
            found = locate(doc, sentence)
            if found is not None:
                page, needles = found.page, found.needles
                self._rects = found.rects
        self._page = page
        return Item(
            citing_id=citing_id,
            ordinal=ordinal,
            section=str(r[11] or "(unknown)"),
            sentence=sentence,
            abstract=str(r[5] or ""),
            citing=Paper(
                str(r[0]), str(r[1] or ""), str(r[2] or ""), cast(int | None, r[3]), str(r[4] or "")
            ),
            cited=Paper(
                str(r[6] or ""),
                str(r[7] or ""),
                str(r[8] or ""),
                cast(int | None, r[9]),
                str(r[10] or ""),
            ),
            pages=pages,
            page=page,
            needles=needles,
            hint_intent=str(r[13] or ""),
        )

    def document(self, citing_id: int, ordinal: int, arxiv_id: str) -> pymupdf.Document | None:
        """
        The open PDF for one item, kept until the session moves on
        """
        if self._doc_key == (citing_id, ordinal) and self._doc is not None:
            return self._doc
        if self._doc is not None:
            self._doc.close()
        path = local_pdf(arxiv_id)
        self._doc = None if path is None else open_pdf(path)
        self._doc_key = (citing_id, ordinal)
        return self._doc

    def page_png(self, citing_id: int, ordinal: int, page: int) -> bytes | None:
        """
        One page of the item on screen, highlighted where the sentence was located
        """
        if self._doc_key != (citing_id, ordinal) or self._doc is None:
            return None
        if not 0 <= page < self._doc.page_count:
            return None
        rects = self._rects if page == self._page else []
        return render(self._doc, page, rects=rects)

    def record(self, citing_id: int, ordinal: int, labels: dict[str, str], ms: int) -> None:
        """
        Append one label, flushed per line so a crash loses nothing
        """
        key = self.key(citing_id, ordinal)
        row: dict[str, object] = {
            "key": key,
            "labels": labels,
            "labeler": self.labeler,
            "ms": ms,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "citing_id": citing_id,
            "ordinal": ordinal,
        }
        with open(self.out, "a", encoding="utf-8") as f:
            _ = f.write(json.dumps(row) + "\n")
            f.flush()
        self.done[key] = row

    def undo(self) -> None:
        """
        Drop the most recent label and rewrite the file
        """
        if not self.done:
            return
        del self.done[list(self.done)[-1]]
        with open(self.out, "w", encoding="utf-8") as f:
            for row in self.done.values():
                _ = f.write(json.dumps(row) + "\n")


class _Handler(BaseHTTPRequestHandler):
    """
    The four routes: the page, the state, a rendered page image, and the two writes
    """

    store: Store

    def _send(self, code: int, body: bytes, mime: str) -> None:
        """
        One response with its length and type
        """
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """
        Serve the page, the current state, or one rendered PDF page
        """
        parts = urlparse(self.path)
        if parts.path == "/api/state":
            pair = self.store.next_pair()
            item = self.store.item(*pair) if pair else None
            payload = {
                "done": len(self.store.done),
                "total": len(self.store.pairs),
                "axes": AXES,
                "item": None if item is None else asdict(item),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        if parts.path == "/api/page":
            q = parse_qs(parts.query)
            citing_id = int(q["citing_id"][0])
            ordinal = int(q["ordinal"][0])
            page = int(q["page"][0])
            png = self.store.page_png(citing_id, ordinal, page)
            if png is None:
                self._send(404, b"no page", "text/plain")
                return
            self._send(200, png, "image/png")
            return
        self._send(200, html().encode(), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        """
        Record a label or undo the last one
        """
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path.startswith("/api/undo"):
            self.store.undo()
            self._send(200, b'{"ok":true}', "application/json")
            return
        body = cast(dict[str, Any], json.loads(raw))  # pyright: ignore[reportExplicitAny]
        self.store.record(
            int(body["citing_id"]),
            int(body["ordinal"]),
            {str(k): str(v) for k, v in dict(body["labels"]).items()},
            int(body.get("ms", 0)),
        )
        self._send(200, b'{"ok":true}', "application/json")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """
        Silence per-request logging
        """


def serve(
    queue: Path = QUEUE,
    out: Path = LABELS,
    labeler: str = "kuroma",
    port: int = 6767,
    host: str = "127.0.0.1",
) -> None:
    """
    Run the labeling app until Ctrl-C
    """
    store = Store(queue, out, labeler)
    _Handler.store = store
    httpd = ThreadingHTTPServer((host, port), _Handler)
    left = len(store.pairs) - len(store.done)
    shown = "127.0.0.1" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"labeling: {left} left -> http://{shown}:{port}  (Ctrl-C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{len(store.done)}/{len(store.pairs)} labeled -> {out}", flush=True)
