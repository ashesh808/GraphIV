"""
Doomscroll: keyboard-driven human labeling, at roughly three seconds an item

One job: show an item, record a judgment, append a JSONL row
One fsynced line per label makes it crash-safe, and a labeled key is skipped on restart
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_AXES: list[dict[str, Any]] = [  # pyright: ignore[reportExplicitAny]
    {
        "name": "intent",
        "keys": "123456",
        "options": [
            "extends",
            "uses",
            "compares",
            "critiques",
            "motivates",
            "background",
        ],
    },
]


def _key_of(item: dict[str, Any], idx: int) -> str:  # pyright: ignore[reportExplicitAny]
    """
    Stable item key: citing_id:ordinal when present, else the input index
    """
    if "citing_id" in item and "ordinal" in item:
        return f"{item['citing_id']}:{item['ordinal']}"
    return f"idx:{idx}"


@dataclass
class Session:
    """
    Labeling state: items in input order, done-set from the output file
    """

    items: list[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    keys: list[str]
    out_path: Path
    labeler: str
    axes: list[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    done: dict[str, dict[str, Any]]  # pyright: ignore[reportExplicitAny]

    @staticmethod
    def load(
        input_path: Path,
        out_path: Path,
        labeler: str,
        axes: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
    ) -> Session:
        """
        Read items and any existing labels (resume support)
        """
        items: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))  # pyright: ignore[reportAny]
        keys = [_key_of(it, i) for i, it in enumerate(items)]
        done: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
        if out_path.exists():
            with open(out_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        row: dict[str, Any] = json.loads(line)  # pyright: ignore[reportExplicitAny]
                        done[str(row["key"])] = row
        return Session(
            items=items,
            keys=keys,
            out_path=out_path,
            labeler=labeler,
            axes=axes,
            done=done,
        )

    def next_index(self) -> int | None:
        """
        Index of the first unlabeled item, or None when finished
        """
        for i, k in enumerate(self.keys):
            if k not in self.done:
                return i
        return None

    def record(self, key: str, labels: dict[str, str], ms: int) -> None:
        """
        Append one label row (fsync per line, a crash loses nothing)
        """
        row: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
            "key": key,
            "labels": labels,
            "labeler": self.labeler,
            "ms": ms,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        idx = self.keys.index(key) if key in self.keys else -1
        if idx >= 0:
            for f_ in ("citing_id", "ordinal"):
                if f_ in self.items[idx]:
                    row[f_] = self.items[idx][f_]
        with open(self.out_path, "a") as f:
            _ = f.write(json.dumps(row) + "\n")
            f.flush()
        self.done[key] = row

    def undo(self) -> str | None:
        """
        Remove the most recent label (rewrites the output file)
        """
        if not self.done:
            return None
        last = list(self.done)[-1]
        del self.done[last]
        with open(self.out_path, "w") as f:
            for row in self.done.values():
                _ = f.write(json.dumps(row) + "\n")
        return last


_PAGE = """<!doctype html>
<meta charset="utf-8"><title>doomscroll</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 16px/1.5 system-ui, sans-serif; max-width: 780px; margin: 2rem auto; padding: 0 1rem; }
  #bar { height: 6px; background: #8883; border-radius: 3px; margin-bottom: 1rem; }
  #fill { height: 100%; background: #4a8; border-radius: 3px; width: 0; transition: width .15s; }
  #count { color: #888; font-size: 13px; margin-bottom: 1rem; }
  .card { border: 1px solid #8884; border-radius: 10px; padding: 1.2rem 1.4rem; }
  .ctx { font-size: 17px; margin: .6rem 0 1rem; }
  .meta { font-size: 13px; color: #888; margin: .15rem 0; }
  .meta b { color: inherit; }
  .axes { display: flex; gap: 2rem; margin-top: 1rem; flex-wrap: wrap; }
  .axis h4 { margin: 0 0 .3rem; font-size: 12px; text-transform: uppercase; color: #888; }
  .opt { padding: .15rem .5rem; border-radius: 6px; margin: .1rem 0; font-size: 14px; }
  .opt kbd { display: inline-block; width: 1.4em; text-align: center; background: #8882;
             border-radius: 4px; margin-right: .5em; font-family: inherit; }
  .opt.sel { background: #4a83; outline: 1px solid #4a8; }
  #help { color: #888; font-size: 13px; margin-top: 1rem; }
  #fin { font-size: 22px; text-align: center; margin-top: 4rem; display: none; }
</style>
<div id="bar"><div id="fill"></div></div>
<div id="count"></div>
<div class="card" id="card"></div>
<div id="help">pick one per axis &middot; auto-advances when complete &middot; <b>u</b> undo &middot; <b>x</b> skip</div>
<div id="fin">done. every item labeled.</div>
<script>
let axes = [], item = null, key = null, picked = {}, t0 = 0;
async function load() {
  const s = await (await fetch('api/state')).json();
  axes = s.axes;
  document.getElementById('fill').style.width = (100 * s.done / s.total) + '%';
  document.getElementById('count').textContent = s.done + ' / ' + s.total;
  if (!s.item) {
    document.getElementById('card').style.display = 'none';
    document.getElementById('help').style.display = 'none';
    document.getElementById('fin').style.display = 'block';
    return;
  }
  item = s.item; key = s.key; picked = {}; t0 = Date.now();
  render();
}
function render() {
  const c = document.getElementById('card');
  let h = '';
  if (item.context) h += '<div class="ctx">' + esc(item.context) + '</div>';
  for (const [k, v] of Object.entries(item))
    if (!['context'].includes(k))
      h += '<div class="meta"><b>' + esc(k) + ':</b> ' + esc(String(v)) + '</div>';
  h += '<div class="axes">';
  for (const ax of axes) {
    h += '<div class="axis"><h4>' + esc(ax.name) + '</h4>';
    ax.options.forEach((opt, i) => {
      const sel = picked[ax.name] === opt ? ' sel' : '';
      h += '<div class="opt' + sel + '"><kbd>' + ax.keys[i] + '</kbd>' + esc(opt) + '</div>';
    });
    h += '</div>';
  }
  h += '</div>';
  c.innerHTML = h;
}
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
async function submit(labels) {
  await fetch('api/label', { method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ key, labels, ms: Date.now() - t0 }) });
  await load();
}
document.addEventListener('keydown', async e => {
  if (e.key === 'u') { await fetch('api/undo', { method: 'POST' }); await load(); return; }
  if (!item) return;
  if (e.key === 'x') { await submit({ _skipped: 'true' }); return; }
  for (const ax of axes) {
    const i = ax.keys.indexOf(e.key);
    if (i >= 0) {
      picked[ax.name] = ax.options[i];
      if (axes.every(a => picked[a.name])) { await submit(picked); return; }
      render(); return;
    }
  }
});
load();
</script>
"""


class _Handler(BaseHTTPRequestHandler):
    """
    Three routes: GET / (page), GET /api/state, POST /api/{label,undo}
    """

    session: Session  # set by serve()

    def _json(self, obj: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """
        Serve the page or the current state
        """
        s = self.session
        if self.path.startswith("/api/state"):
            idx = s.next_index()
            self._json(
                {
                    "total": len(s.items),
                    "done": len(s.done),
                    "axes": s.axes,
                    "item": s.items[idx] if idx is not None else None,
                    "key": s.keys[idx] if idx is not None else None,
                }
            )
            return
        body = _PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        """
        Record or undo a label
        """
        s = self.session
        if self.path.startswith("/api/undo"):
            _ = s.undo()
            self._json({"ok": True})
            return
        if self.path.startswith("/api/label"):
            n = int(self.headers.get("Content-Length", "0"))
            payload: dict[str, Any] = json.loads(  # pyright: ignore[reportExplicitAny]
                self.rfile.read(n)
            )
            labels = {
                str(k): str(v) for k, v in dict(payload["labels"]).items()
            }  # pyright: ignore[reportAny]
            s.record(
                str(payload["key"]), labels, int(payload.get("ms", 0))
            )  # pyright: ignore[reportAny]
            self._json({"ok": True})
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """
        Silence per-request logging (silence is golden)
        """


def serve(session: Session, port: int, host: str = "127.0.0.1") -> None:
    """
    Run the labeling server until Ctrl-C
    """
    _Handler.session = session
    httpd = ThreadingHTTPServer((host, port), _Handler)
    left = len(session.items) - len(session.done)
    shown = "127.0.0.1" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"doomscroll: {left} to label -> http://{shown}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{len(session.done)}/{len(session.items)} labeled -> {session.out_path}")


def to_pg(labels_path: Path) -> None:
    """
    Upsert intent labels into gold_label (source of truth for eval)

    Rows without citing_id/ordinal or with only a skip marker are ignored.
    """
    import psycopg

    from graphiv.core.config import Config

    cfg = Config.load()
    rows: list[tuple[int, int, str | None, str]] = []
    with open(labels_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row: dict[str, Any] = json.loads(line)  # pyright: ignore[reportExplicitAny]
            labels = dict(row.get("labels", {}))  # pyright: ignore[reportAny]
            if "citing_id" not in row or "_skipped" in labels:
                continue
            rows.append(
                (
                    int(row["citing_id"]),  # pyright: ignore[reportAny]
                    int(row["ordinal"]),  # pyright: ignore[reportAny]
                    labels.get("intent"),
                    str(row.get("labeler", "human")),  # pyright: ignore[reportAny]
                )
            )
    if not rows:
        print("no pushable rows (need citing_id/ordinal, non-skipped)")
        return
    with psycopg.connect(cfg.pg_dsn) as conn:
        cur = conn.cursor()
        _ = cur.executemany(
            "INSERT INTO gold_label (citing_id, ordinal, intent, labeler) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (citing_id, ordinal) DO UPDATE SET intent = EXCLUDED.intent, "
            "labeler = EXCLUDED.labeler, labeled_at = now()",
            rows,
        )
        conn.commit()
    print(f"upserted {len(rows)} rows into gold_label")


def main() -> None:
    """
    CLI entry
    """
    ap = argparse.ArgumentParser(description="keyboard-driven human labeling")
    _ = ap.add_argument("--input", type=Path, help="items JSONL")
    _ = ap.add_argument("--out", type=Path, help="labels JSONL (appended, resumable)")
    _ = ap.add_argument("--labeler", default="kuroma")
    _ = ap.add_argument("--port", type=int, default=8787)
    _ = ap.add_argument("--host", default="127.0.0.1", help="bind address")
    _ = ap.add_argument("--axes", type=Path, help="axes JSON override")
    _ = ap.add_argument("--to-pg", type=Path, help="push a labels JSONL into gold_label")
    _ = ap.add_argument(
        "--pdf", action="store_true", help="the citation labeling app, with the paper on screen"
    )
    ns = ap.parse_args()

    to_pg_path: Path | None = ns.to_pg  # pyright: ignore[reportAny]
    if to_pg_path is not None:
        to_pg(to_pg_path)
        return
    input_path: Path | None = ns.input  # pyright: ignore[reportAny]
    out_path: Path | None = ns.out  # pyright: ignore[reportAny]
    if bool(ns.pdf):  # pyright: ignore[reportAny]
        from graphiv.preprocess.label.webapp import LABELS, QUEUE
        from graphiv.preprocess.label.webapp import serve as serve_pdf

        serve_pdf(
            queue=input_path or QUEUE,
            out=out_path or LABELS,
            labeler=str(ns.labeler),  # pyright: ignore[reportAny]
            port=int(ns.port),  # pyright: ignore[reportAny]
            host=str(ns.host),  # pyright: ignore[reportAny]
        )
        return
    if input_path is None or out_path is None:
        ap.error("--input and --out are required to serve")
        return
    axes = DEFAULT_AXES
    axes_path: Path | None = ns.axes  # pyright: ignore[reportAny]
    if axes_path is not None:
        with open(axes_path) as f:
            axes = json.load(f)  # pyright: ignore[reportAny]
    session = Session.load(
        input_path, out_path, str(ns.labeler), axes
    )  # pyright: ignore[reportAny]
    serve(session, int(ns.port), str(ns.host))  # pyright: ignore[reportAny]


if __name__ == "__main__":
    main()
