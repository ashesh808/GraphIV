"""
The gold-label web tool: hand-label citation intent and polarity one at a time

Labels land in the gold_label table, which the human benchmark reads from
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg

_REPO = Path(__file__).resolve().parents[3]
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={_REPO}/.pg port=5433 dbname=arxivkg")
PORT = int(os.environ.get("GOLD_TOOL_PORT", "8765"))
INTENTS = ["uses", "extends", "compares", "motivates", "background", "critiques"]
POLARITIES = ["negative", "neutral", "positive"]

_PAGE = """<!doctype html><html><head><meta charset=utf-8><title>gold labeler</title>
<style>
 :root{--bg:#0C0F1E;--fg:#D4D0EA;--sv:#171D36;--ol:#232E4C;--pri:#F07898;--sec:#6FC898}
 body{background:var(--bg);color:var(--fg);font-family:'Google Sans Flex',system-ui,sans-serif;
   margin:0;padding:2rem;display:flex;flex-direction:column;align-items:center}
 .card{background:var(--sv);border:1px solid var(--ol);border-radius:14px;max-width:780px;
   padding:1.5rem 1.8rem;margin-top:1rem}
 .sec{color:var(--sec);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
 .sent{font-size:1.25rem;line-height:1.6;margin:.8rem 0}
 .cite{color:var(--pri);font-weight:600}
 .meta{color:#8B95A8;font-size:.85rem;margin-top:.6rem}
 .row{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.2rem}
 .btn{background:var(--bg);border:1px solid var(--ol);color:var(--fg);border-radius:9px;
   padding:.5rem .8rem;cursor:pointer;font-size:.95rem}
 .btn.on{background:var(--pri);color:var(--bg);border-color:var(--pri)}
 .btn.pol.on{background:var(--sec);color:var(--bg);border-color:var(--sec)}
 kbd{background:var(--ol);border-radius:4px;padding:0 .3rem;font-size:.8rem}
 #count{color:#8B95A8;margin-top:1rem}
</style></head><body>
 <h2>arxivkg · gold intent/polarity labeler</h2>
 <div id=count>loading…</div>
 <div class=card id=card><div class=sec id=sec></div><div class=sent id=sent></div>
   <div class=meta id=meta></div>
   <div class=row id=intents></div><div class=row id=pols></div></div>
<script>
const INT=["uses","extends","compares","motivates","background","critiques"];
const POL=["negative","neutral","positive"];
let cur=null,iSel=null,pSel=null;
function render(){
 document.getElementById('intents').innerHTML=INT.map((x,i)=>
   `<button class="btn ${iSel===x?'on':''}" onclick="pick('i','${x}')"><kbd>${i+1}</kbd> ${x}</button>`).join('');
 document.getElementById('pols').innerHTML=POL.map((x,i)=>
   `<button class="btn pol ${pSel===x?'on':''}" onclick="pick('p','${x}')"><kbd>${'zxc'[i]}</kbd> ${x}</button>`).join('');
}
async function load(){
 iSel=pSel=null;
 const r=await fetch('/api/next');const d=await r.json();cur=d.item;
 document.getElementById('count').innerHTML=`labeled <b>${d.n_labeled}</b> · remaining pool ~${d.pool}`;
 if(!cur){document.getElementById('sent').innerText='no more unlabeled citations 🎉';return;}
 document.getElementById('sec').innerText=cur.section||'(no section)';
 document.getElementById('sent').innerHTML=(cur.sentence||'').replace(/\\[CITE\\]/g,'<span class=cite>[CITE]</span>');
 document.getElementById('meta').innerText='→ cites: '+(cur.cited_title||cur.cited_arxiv||'?');
 render();
}
function pick(k,v){ if(k==='i')iSel=v; else pSel=v; render(); if(iSel&&pSel)submit(); }
async function submit(){
 await fetch('/api/label',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({citing_id:cur.citing_id,ordinal:cur.ordinal,intent:iSel,polarity:pSel})});
 load();
}
document.addEventListener('keydown',e=>{
 const k=e.key.toLowerCase();
 if(k>='1'&&k<='6')pick('i',INT[+k-1]);
 else if('zxc'.includes(k))pick('p',POL['zxc'.indexOf(k)]);
 else if(k==='s')load();
});
load();
</script></body></html>"""


def _conn() -> psycopg.Connection[tuple[Any, ...]]:
    return psycopg.connect(PG_DSN, autocommit=True)


def _next_item() -> dict[str, Any] | None:
    sql = cast(
        LiteralString,
        "SELECT c.citing_id, c.ordinal, c.section, c.sentence, pd.arxiv_id, m.title "
        "FROM citation c LEFT JOIN gold_label g ON g.citing_id=c.citing_id AND g.ordinal=c.ordinal "
        "LEFT JOIN paper pd ON pd.id=c.cited_id LEFT JOIN paper_meta m ON m.arxiv_id=pd.arxiv_id "
        "WHERE c.cited_id IS NOT NULL AND c.sentence IS NOT NULL AND g.citing_id IS NULL "
        "AND length(c.sentence) BETWEEN 60 AND 600 "
        "ORDER BY random() LIMIT 1",
    )
    with _conn() as conn:
        r = conn.execute(sql).fetchone()
        n = conn.execute("SELECT count(*) FROM gold_label").fetchone()
    if not r:
        return {"item": None, "n_labeled": int(n[0]) if n else 0, "pool": 0}
    return {
        "item": {
            "citing_id": int(r[0]),
            "ordinal": int(r[1]),
            "section": r[2],
            "sentence": r[3],
            "cited_arxiv": r[4],
            "cited_title": r[5],
        },
        "n_labeled": int(n[0]) if n else 0,
        "pool": 70_000_000,
    }


def _save(d: dict[str, Any]) -> None:
    with _conn() as conn:
        _ = conn.execute(
            "INSERT INTO gold_label (citing_id, ordinal, intent, polarity, labeler) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (citing_id, ordinal) DO UPDATE "
            "SET intent=EXCLUDED.intent, polarity=EXCLUDED.polarity, labeled_at=now()",
            (
                d["citing_id"],
                d["ordinal"],
                d["intent"],
                d["polarity"],
                os.environ.get("USER", "human"),
            ),
        )


class _H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send(200, _PAGE.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/next":
            self._send(200, json.dumps(_next_item()).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/label":
            n = int(self.headers.get("Content-Length", "0"))
            d = cast("dict[str, Any]", json.loads(self.rfile.read(n) or b"{}"))
            if d.get("intent") in INTENTS and d.get("polarity") in POLARITIES:
                _save(d)
            self._send(200, b"{}", "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, format: str, *args: Any) -> None:  # quiet  # noqa: A002
        _ = (format, args)


def main() -> None:
    print(f"[gold] http://localhost:{PORT}  (Ctrl-C to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), _H).serve_forever()


if __name__ == "__main__":
    main()
