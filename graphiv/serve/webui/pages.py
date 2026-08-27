"""
The two rendered pages: the library index and a single run's reading view

Both are assembled from the shared shell so the theme and settings popover stay identical.
"""

from __future__ import annotations

import html as html_mod
import json

from graphiv.generate.graph_viz import GRAPH_JS
from graphiv.serve.webui.scripts import (
    _INDEX_JS,
    _RUN_JS,
    _STAGE_COLORS,
    _THEME_JS,
    _UI_JS,
)
from graphiv.serve.webui.theme import _CSS, _FONTS, _settings_menu


def _page(title: str, body: str, head: str = "", script: str = "", public: bool = False) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{_FONTS}<style>{_CSS}</style>
<script>{_THEME_JS}</script>{head}</head><body>
<nav class="navbar">
<a class="brand" href="/"><b>GraphIV</b><span>Research Library</span></a>
<span class="right">{_settings_menu()}</span></nav>
<main>{body}</main>{'' if public else '<script src="/admin.js"></script>'}<script>{_UI_JS}{script}</script></body></html>"""


def _index_html(public: bool = False) -> str:
    body = """<header class="hero">
 <h1>Research Library</h1>
 <p class="sub" id="count">&hellip;</p>
 <div class="searchwrap">
  <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
  <input type="search" id="q" placeholder="Search research topics&hellip;">
 </div>
</header>
<div class="controls">
 <span class="pager" id="pager"></span>
 <select class="pill sm" id="per">
  <option value="15" selected>15 per page</option>
  <option value="30">30 per page</option>
  <option value="60">60 per page</option>
  <option value="100000">show all</option>
 </select>
</div>
<div class="grid" id="grid">loading&hellip;</div>"""
    return _page("GraphIV Research Library", body, script=_INDEX_JS, public=public)


def _run_html(slug: str, cfg: str, question: str = "", public: bool = False) -> str:
    tabs = (
        ("report", "Report"),
        ("references", "References"),
        ("graph", "Graph"),
        ("figures", "Figures"),
        ("details", "Details"),
    )
    tab_btns = "".join(
        f'<button data-t="{t}" onclick="tab(\'{t}\')">{label}</button>' for t, label in tabs
    )
    dl = "".join(
        f'<a class="mi mono" href="/files/{slug}/{cfg}/{f}" target="_blank">{f}</a>'
        for f in (
            "report.md",
            "report.tex",
            "refs.bib",
            "report.pdf",
            "papers.json",
            "run.json",
            "digest.txt",
            "graph.html",
        )
    )
    qt = html_mod.escape(question) if question else "&hellip;"
    admin_menu = (
        ""
        if public
        else """<details class="menu"><summary class="ab-btn" title="run actions">&ctdot;</summary>
   <div class="menu-body">
    <button class="mi" onclick="actRun('purge-cache')">Purge caches</button>
    <button class="mi danger" onclick="actRun('delete')">Delete run&hellip;</button>
   </div></details>"""
    )
    body = f"""
<div class="runhead">
 <a class="back" href="/">&larr; Library</a>
 <h1 class="q" id="qtitle">{qt}</h1>
 <div class="byline" id="rbyline"></div>
 <div class="tech mono">{slug} / {cfg}</div>
 <div class="actionbar">
  <button class="ab-btn primary" onclick="openReportPdf()">Read PDF</button>
  <details class="menu"><summary class="ab-btn">Download &#9662;</summary>
   <div class="menu-body">{dl}</div></details>
  {admin_menu}
 </div>
</div>
<div class="tabs">{tab_btns}</div>
<div class="tab-panel" id="p-report"><div id="report-md">loading&hellip;</div></div>
<div class="tab-panel" id="p-references"><div id="refs">loading&hellip;</div></div>
<div class="tab-panel" id="p-graph"><div id="gpanel"></div></div>
<div class="tab-panel" id="p-figures"><div class="figs" id="figgrid">loading&hellip;</div></div>
<div class="tab-panel" id="p-details"><div id="details">loading&hellip;</div></div>
<aside id="panel">
 <div class="panel-head"><b id="panel-t"></b>
  <button class="pill sm" onclick="closePanel()">&#x2715;</button></div>
 <div class="panel-meta" id="panel-m"></div>
 <div class="panel-links" id="panel-l"></div>
 <div class="panel-body" id="panel-b"></div>
</aside>
"""
    run_js = (
        _RUN_JS.replace("__SLUG__", json.dumps(slug))
        .replace("__CFG__", json.dumps(cfg))
        .replace("__STAGES__", _STAGE_COLORS)
    )
    head = (
        '<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>'
        '<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/'
        'vis-network.min.js"></script>'
        "<script>window.Prism={manual:true};</script>"
        '<script src="https://cdn.jsdelivr.net/npm/prismjs@1.30.0/components/'
        'prism-core.min.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/prismjs@1.30.0/plugins/autoloader/'
        'prism-autoloader.min.js"></script>'
        '<link rel="stylesheet" '
        'href="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css">'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/contrib/'
        'auto-render.min.js"></script>'
    )
    title = f"GraphIV: {html_mod.escape(question) if question else slug}"
    return _page(title, body, head=head, script=GRAPH_JS + "\n" + run_js, public=public)
