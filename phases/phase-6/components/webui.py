"""GraphIV research library, served by the MCP http transport (caddy vhost graphiv.<host>).

Index `/` is a library of completed research: hero search over run cards (question in a
serif display face, humanized byline, per-card action menu), pagination, live progress on
running cards. `/run/<slug>/<cfg>` is the reading view: report (client-rendered md, asset
urls rewritten to /files, citation links get hover previews + open the paper pdf in a
page-level slide-over panel), References (every cohort paper with its reader summary,
filter/sort/search), interactive story graph (shared renderer from graph_viz: toolbar
search, role filters, neighbor focus), figures, and a Details tab (judge transcript,
grouped timings, metadata). Actions are consolidated into menus; every confirmation and
result is a modal popup. Technical identifiers (slugs, arxiv ids, cosine scores) are
hidden behind a global "show technical ids" toggle so entries read as a library, not a
debug console. Design language mirrors kkuroma.github.io: the four shunka-shuutou
seasonal palettes (Haruhana/Natsumikan/Akiba/Fuyuyuki, light+dark, localStorage).
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_mod
import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from starlette.requests import Request
    from starlette.responses import Response

from _common import DATA_DIR
from graph_viz import GRAPH_CSS, GRAPH_JS

_GRADE_DB = DATA_DIR / "metadata" / "grade_cache.db"
_CRIT_DB = DATA_DIR / "metadata" / "critique_cache.db"

# The four shunka-shuutou palettes from kkuroma.github.io themes.js (subset of vars used here).
_PALETTES: dict[str, dict[str, dict[str, str]]] = {
    "haruhana": {
        "light": {
            "base": "#EFF0F8",
            "mantle": "#FFFFFF",
            "crust": "#e1e2ed",
            "text": "#252535",
            "subtext1": "#393947",
            "subtext0": "#565662",
            "surface2": "#C8C8D8",
            "surface1": "#d4d4e2",
            "surface0": "#dddeea",
            "overlay1": "#848491",
            "overlay0": "#a0a0af",
            "primary": "#C04868",
            "secondary": "#6248B8",
            "tertiary": "#2A8A60",
            "red": "#B00020",
            "yellow": "#8A6A00",
            "green": "#2A8A60",
            "sky": "#1E7AA8",
        },
        "dark": {
            "base": "#0C0F1E",
            "mantle": "#171D36",
            "crust": "#090B15",
            "text": "#D4D0EA",
            "subtext1": "#babbd3",
            "subtext0": "#8B95A8",
            "surface2": "#424D68",
            "surface1": "#2B3758",
            "surface0": "#232E4C",
            "overlay1": "#6a758b",
            "overlay0": "#58637b",
            "primary": "#F07898",
            "secondary": "#B4A2E8",
            "tertiary": "#6FC898",
            "red": "#FF5370",
            "yellow": "#F8D06A",
            "green": "#6FC898",
            "sky": "#8AD4F0",
        },
    },
    "natsumikan": {
        "light": {
            "base": "#EEF0F5",
            "mantle": "#FFFFFF",
            "crust": "#e1e4eb",
            "text": "#272B32",
            "subtext1": "#3a3e47",
            "subtext0": "#565B66",
            "surface2": "#C8CDD8",
            "surface1": "#d3d8e1",
            "surface0": "#dde0e8",
            "overlay1": "#848994",
            "overlay0": "#a0a5b0",
            "primary": "#C15A20",
            "secondary": "#8F5A00",
            "tertiary": "#006070",
            "red": "#B00020",
            "yellow": "#8F5A00",
            "green": "#4A7C59",
            "sky": "#2878A0",
        },
        "dark": {
            "base": "#0D1017",
            "mantle": "#171D26",
            "crust": "#0A0C12",
            "text": "#D1D1C7",
            "subtext1": "#babcb9",
            "subtext0": "#8E959E",
            "surface2": "#464B5D",
            "surface1": "#253040",
            "surface0": "#242C3A",
            "overlay1": "#6e7481",
            "overlay0": "#5c6170",
            "primary": "#F5803E",
            "secondary": "#FFB454",
            "tertiary": "#39BAE6",
            "red": "#FF5370",
            "yellow": "#FFB454",
            "green": "#AAD94C",
            "sky": "#6BD2F0",
        },
    },
    "akiba": {
        "light": {
            "base": "#F0EAE4",
            "mantle": "#FFFFFF",
            "crust": "#e8ded7",
            "text": "#2A1E18",
            "subtext1": "#40322c",
            "subtext0": "#60504A",
            "surface2": "#D8C8C0",
            "surface1": "#dfd2cb",
            "surface0": "#e5dbd4",
            "overlay1": "#908079",
            "overlay0": "#ae9e97",
            "primary": "#902020",
            "secondary": "#806000",
            "tertiary": "#507840",
            "red": "#A82828",
            "yellow": "#806000",
            "green": "#507840",
            "sky": "#3088B8",
        },
        "dark": {
            "base": "#141210",
            "mantle": "#221D1A",
            "crust": "#0F0D0B",
            "text": "#DDD0C0",
            "subtext1": "#c6b8aa",
            "subtext0": "#9C8C80",
            "surface2": "#484038",
            "surface1": "#403530",
            "surface0": "#362D28",
            "overlay1": "#766a60",
            "overlay0": "#61574e",
            "primary": "#C84040",
            "secondary": "#DCA561",
            "tertiary": "#98BB6C",
            "red": "#C84040",
            "yellow": "#DCA561",
            "green": "#98BB6C",
            "sky": "#90CCE0",
        },
    },
    "fuyuyuki": {
        "light": {
            "base": "#EDF2F8",
            "mantle": "#FFFFFF",
            "crust": "#dde5ed",
            "text": "#202530",
            "subtext1": "#333946",
            "subtext0": "#505868",
            "surface2": "#C0CCD8",
            "surface1": "#ced7e2",
            "surface0": "#d9e1ea",
            "overlay1": "#7d8695",
            "overlay0": "#99a3b1",
            "primary": "#2878C8",
            "secondary": "#186878",
            "tertiary": "#4060A8",
            "red": "#B00020",
            "yellow": "#806800",
            "green": "#287848",
            "sky": "#2E86B0",
        },
        "dark": {
            "base": "#0B0E18",
            "mantle": "#141C30",
            "crust": "#080A10",
            "text": "#CDD8E8",
            "subtext1": "#b3c0d1",
            "subtext0": "#8492A6",
            "surface2": "#384860",
            "surface1": "#273654",
            "surface0": "#202D46",
            "overlay1": "#627186",
            "overlay0": "#4f5e75",
            "primary": "#78B4E8",
            "secondary": "#7CD4DC",
            "tertiary": "#A0B8E8",
            "red": "#FF5370",
            "yellow": "#D4C870",
            "green": "#7CD4A0",
            "sky": "#94DCF0",
        },
    },
}

_PALETTE_LABEL = {
    "haruhana": "Haruhana 春",
    "natsumikan": "Natsumikan 夏",
    "akiba": "Akiba 秋",
    "fuyuyuki": "Fuyuyuki 冬",
}


def _theme_css() -> str:
    blocks: list[str] = []
    for pal, modes in _PALETTES.items():
        for mode, colors in modes.items():
            sel = f'[data-palette="{pal}"][data-mode="{mode}"]'
            if pal == "haruhana" and mode == "light":
                sel = ":root," + sel
            body = ";".join(f"--{k}:{v}" for k, v in colors.items())
            blocks.append(sel + "{" + body + "}")
    return "\n".join(blocks)


_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    "?family=Newsreader:ital,opsz,wght@0,6..72,400..700;1,6..72,400..700"
    "&family=Inter:wght@400;500;600;700"
    '&family=JetBrains+Mono:wght@400;500&display=swap">'
)

_CSS = (
    _theme_css()
    + """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Noto Sans',-apple-system,'Segoe UI',sans-serif;
background:var(--base);color:var(--text);line-height:1.6;font-size:15px;
transition:background .3s,color .3s;-webkit-font-smoothing:antialiased}
h1,h2,h3,.q{font-family:'Newsreader',Georgia,serif;font-weight:600}
code,pre,.mono{font-family:'JetBrains Mono','Maple Mono',ui-monospace,monospace;font-size:.86em}
a{color:var(--primary)}
[data-ids="off"] .tech{display:none!important}
[data-public="on"] .adminonly{display:none!important}
.navbar{display:flex;align-items:center;justify-content:space-between;gap:.75rem;
padding:.55rem clamp(.9rem,3vw,1.6rem);background:var(--mantle);
border-bottom:1px solid var(--surface1);position:sticky;top:0;z-index:1000}
.brand{display:flex;align-items:baseline;gap:.6rem;text-decoration:none;color:var(--text)}
.brand b{font-family:'Newsreader',Georgia,serif;font-size:1.3rem;font-weight:600}
.brand span{font-size:.78rem;color:var(--subtext0);letter-spacing:.5px}
.navbar .right{display:flex;gap:.45rem;align-items:center}
.pill{border:1px solid var(--surface2);border-radius:9999px;font-family:inherit;
font-size:.85rem;color:var(--text);background:var(--mantle);padding:.38rem .95rem;
cursor:pointer;transition:all .18s;text-decoration:none;display:inline-block;line-height:1.45}
.pill:hover{background:var(--surface0);border-color:var(--overlay0)}
.pill:disabled{opacity:.4;cursor:default}
.pill.sm{font-size:.75rem;padding:.2rem .65rem}
.pill.danger{color:var(--red);border-color:var(--red)}
.pill.danger:hover{background:var(--red);color:var(--mantle)}
select.pill{appearance:none}
details.menu{position:relative}
details.menu summary{list-style:none;cursor:pointer}
details.menu summary::-webkit-details-marker{display:none}
.menu-body{position:absolute;right:0;top:calc(100% + 6px);background:var(--mantle);
border:1px solid var(--surface2);border-radius:12px;box-shadow:0 12px 34px rgba(0,0,0,.22);
padding:.4rem;min-width:190px;z-index:1200;display:flex;flex-direction:column;gap:2px}
details.menu.up .menu-body{top:auto;bottom:calc(100% + 6px)}
.mi{display:block;text-align:left;background:none;border:0;border-radius:8px;
padding:.42rem .65rem;font:inherit;font-size:.85rem;color:var(--text);cursor:pointer;
text-decoration:none;white-space:nowrap}
.mi:hover{background:var(--surface0)}
.mi.danger{color:var(--red)}
.m-label{font-size:.66rem;letter-spacing:.7px;text-transform:uppercase;
color:var(--overlay1);padding:.4rem .65rem .1rem}
.mrow{display:flex;gap:.45rem;padding:.3rem .65rem;align-items:center}
.swatch{width:26px;height:26px;border-radius:50%;border:2px solid transparent;
cursor:pointer;padding:0}
.swatch.active{border-color:var(--text)}
.seg{display:flex;border:1px solid var(--surface2);border-radius:9999px;overflow:hidden;
padding:0;margin:.25rem .65rem}
.mode-btn{flex:1;border:0;background:none;padding:.32rem .9rem;font:inherit;
font-size:.8rem;color:var(--subtext0);cursor:pointer}
.mode-btn.active{background:var(--surface1);color:var(--text)}
label.chk{font-size:.83rem;color:var(--subtext1);cursor:pointer;white-space:nowrap}
main{padding:1rem clamp(1rem,4vw,2.5rem) 4rem;max-width:1280px;margin:0 auto}
.hero{text-align:center;padding:2rem 0 1.2rem}
.hero h1{font-size:clamp(1.8rem,4vw,2.5rem);letter-spacing:.3px}
.hero .sub{color:var(--subtext0);font-size:.92rem;margin:.3rem 0 1.2rem}
.searchwrap{max-width:640px;margin:0 auto;position:relative}
.searchwrap svg{position:absolute;left:1.05rem;top:50%;transform:translateY(-50%);
width:15px;height:15px;stroke:var(--overlay1);fill:none;stroke-width:2}
.searchwrap input{width:100%;padding:.72rem 1.2rem .72rem 2.6rem;border-radius:9999px;
border:1px solid var(--surface2);background:var(--mantle);color:var(--text);font:inherit;
font-size:.95rem;outline:none;box-shadow:0 3px 14px rgba(0,0,0,.07)}
.searchwrap input:focus{border-color:var(--primary)}
.controls{display:flex;justify-content:flex-end;align-items:center;margin:.3rem 0 1rem;
gap:.7rem;flex-wrap:wrap}
.pager{display:flex;gap:.45rem;align-items:center;font-size:.84rem;color:var(--subtext0)}
.grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fill,minmax(310px,1fr))}
.card{position:relative;background:var(--mantle);border:1px solid var(--surface1);
border-radius:14px;padding:1.1rem 1.2rem .8rem;display:flex;flex-direction:column;
gap:.4rem;transition:border-color .2s,box-shadow .2s,transform .2s}
.card:hover{border-color:var(--surface2);box-shadow:0 8px 28px rgba(0,0,0,.13);
transform:translateY(-1px)}
.card .q{font-size:1.08rem;font-weight:500;line-height:1.42}
.card .q::first-letter{text-transform:uppercase}
.card .q a{color:inherit;text-decoration:none}
.card .q a::after{content:"";position:absolute;inset:0;border-radius:14px}
.byline{color:var(--subtext0);font-size:.8rem}
.facts{display:flex;flex-wrap:wrap;gap:.1rem .45rem;font-size:.78rem;
color:var(--subtext0)}
.facts b{color:var(--text);font-weight:600}
.facts i{font-style:normal;color:var(--overlay0)}
.card .facts,.card .stagebar{position:relative;z-index:2}
.tech{color:var(--overlay1);font-size:.72rem;word-break:break-all}
.live{display:flex;align-items:center;gap:.45rem;font-size:.8rem;color:var(--yellow)}
.live.gray{color:var(--overlay1)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.pulse{animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.35}}
.stagebar{display:flex;height:5px;border-radius:3px;overflow:hidden;background:var(--surface0)}
.stagebar div{height:100%}
.cardfoot{display:flex;gap:.4rem;justify-content:flex-end;align-items:center;
margin-top:auto;position:relative;z-index:3}
.runhead{margin:.6rem 0 0}
.back{font-size:.83rem;text-decoration:none;color:var(--subtext0)}
.back:hover{color:var(--primary)}
.runhead .q{font-size:clamp(1.3rem,3vw,1.7rem);margin:.35rem 0 .25rem;line-height:1.35;
max-width:62ch;font-weight:500}
.runhead .q::first-letter{text-transform:uppercase}
.actionbar{display:inline-flex;align-items:stretch;margin:.8rem 0 0;
border:1px solid var(--surface2);border-radius:9999px;background:var(--mantle)}
.actionbar>*{border-left:1px solid var(--surface1)}
.actionbar>:first-child{border-left:0}
.ab-btn{display:inline-flex;align-items:center;gap:.3rem;background:none;border:0;
font:inherit;font-size:.85rem;color:var(--text);padding:.4rem 1.05rem;cursor:pointer;
line-height:1.45;white-space:nowrap}
.ab-btn:hover{background:var(--surface0)}
.actionbar>:first-child,.actionbar>:first-child.ab-btn,
.actionbar>:first-child .ab-btn{border-radius:9999px 0 0 9999px}
.actionbar>:last-child,.actionbar>:last-child .ab-btn{border-radius:0 9999px 9999px 0}
.ab-btn.primary{color:var(--primary);font-weight:600}
.tabs{display:flex;gap:.15rem;margin:1.1rem 0 1.1rem;border-bottom:1px solid var(--surface1);
overflow-x:auto;scrollbar-width:none}
.tabs button{border:0;background:none;font:inherit;font-size:.9rem;color:var(--subtext0);
padding:.5rem .9rem;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
.tabs button:hover{color:var(--text)}
.tabs button.active{color:var(--text);border-bottom-color:var(--primary);font-weight:600}
.tab-panel{display:none}.tab-panel.active{display:block}
#report-md{font-family:'Newsreader',Georgia,serif;font-size:1.04rem;line-height:1.75;
background:var(--mantle);border:1px solid var(--surface1);border-radius:16px;
padding:clamp(1.2rem,4vw,2.6rem);max-width:880px;margin:0 auto;overflow-x:auto}
#report-md>h1:first-child{display:none}
#report-md h2{font-size:1.45rem;border-bottom:1px solid var(--surface1);
padding-bottom:.25rem;margin:2.3em 0 .75em}
#report-md h3{font-size:1.15rem;margin:2em 0 .55em}
#report-md p{margin:.85em 0}
#report-md li{margin:.25em 0 .25em 1.3em}
#report-md img{max-width:100%;border-radius:10px;display:block;margin:1rem auto}
#report-md p:has(>img){text-align:center}
#report-md p:has(>img)+p{text-align:center;font-size:.88em;color:var(--subtext0);
max-width:64ch;margin:.3em auto 1.6em}
#report-md a{text-decoration:none;border-bottom:1px dotted var(--primary)}
#report-md table{font-family:'Inter',sans-serif;font-size:.83rem;margin:1rem 0}
#report-md pre{background:var(--surface0);border-radius:8px;padding:.7rem;overflow:auto}
#report-md pre code{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.82rem;
line-height:1.55}
.token.comment,.token.prolog,.token.doctype,.token.cdata{color:var(--overlay1);
font-style:italic}
.token.punctuation{color:var(--subtext0)}
.token.property,.token.tag,.token.boolean,.token.constant,.token.symbol,
.token.deleted{color:var(--red)}
.token.number{color:var(--yellow)}
.token.selector,.token.attr-name,.token.string,.token.char,.token.builtin,
.token.inserted{color:var(--green)}
.token.operator,.token.entity,.token.url{color:var(--sky)}
.token.atrule,.token.attr-value,.token.keyword{color:var(--secondary);font-weight:600}
.token.function,.token.class-name{color:var(--primary)}
.token.regex,.token.important,.token.variable{color:var(--yellow)}
.token.bold,.token.important{font-weight:700}
.token.italic{font-style:italic}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid var(--surface0)}
th{color:var(--subtext0);white-space:nowrap}
.rtools{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin:0 auto 1rem;
max-width:900px}
.rtools input[type=search]{flex:1;min-width:170px;padding:.4rem 1rem;border-radius:9999px;
border:1px solid var(--surface2);background:var(--mantle);color:var(--text);font:inherit;
font-size:.85rem;outline:none}
.rtools input[type=search]:focus{border-color:var(--primary)}
.reflist{display:flex;flex-direction:column;gap:.9rem;max-width:900px;margin:0 auto}
.ref{display:flex;gap:1rem;background:var(--mantle);border:1px solid var(--surface1);
border-radius:14px;padding:1rem 1.15rem}
.ref-main{flex:1;min-width:0}
.ref-t{font-family:'Newsreader',Georgia,serif;font-size:1.05rem;font-weight:500;
line-height:1.4}
.ref-t a{color:var(--text);text-decoration:none}
.ref-t a:hover{color:var(--primary)}
.cited-b{font-size:.6rem;font-weight:700;letter-spacing:.5px;color:var(--tertiary);
border:1px solid var(--tertiary);border-radius:6px;padding:.05rem .35rem;
vertical-align:2px;margin-left:.45rem;white-space:nowrap;font-family:'Inter',sans-serif}
.ref-m{font-size:.8rem;color:var(--subtext0);margin:.18rem 0}
.ref-s{font-size:.88rem;color:var(--subtext1);margin-top:.3rem;line-height:1.55}
.ref-side{display:flex;flex-direction:column;gap:.4rem;align-items:flex-end;flex-shrink:0}
.rolechip{padding:.05rem .45rem;border-radius:9999px;font-size:.7rem;color:#090B15;
font-weight:600;white-space:nowrap;display:inline-block;font-family:'Inter',sans-serif}
.stats{display:flex;gap:.4rem;flex-wrap:wrap;margin:.4rem 0}
.stat{background:var(--surface0);border-radius:10px;padding:.3rem .65rem;font-size:.72rem;
text-align:center;color:var(--subtext0);line-height:1.3}
.stat b{display:block;font-size:.95rem;color:var(--primary)}
.section{background:var(--mantle);border:1px solid var(--surface1);border-radius:14px;
padding:1.1rem 1.3rem;margin-bottom:1rem}
.section h2{font-size:1.2rem;margin-bottom:.6rem}
.section pre{background:var(--surface0);border-radius:8px;padding:.7rem;overflow:auto;
font-size:.75rem}
.trow{display:grid;grid-template-columns:minmax(7rem,11rem) 1fr minmax(5rem,7rem);
align-items:center;gap:.6rem;font-size:.82rem;margin:.3rem 0}
.tbar{height:10px;border-radius:5px;background:var(--surface0);overflow:hidden}
.tbar div{height:100%;border-radius:5px}
.figs{display:grid;gap:.7rem;grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
.fig-th{width:100%;aspect-ratio:1;object-fit:cover;border-radius:10px;
border:1px solid var(--surface1);cursor:pointer;background:#fff;display:block}
.fig-th:hover{border-color:var(--primary)}
.figview{display:flex;align-items:center;gap:.7rem;max-width:min(1200px,96vw)}
.figview figure{background:var(--mantle);border:1px solid var(--surface2);
border-radius:16px;padding:1.1rem;flex:1;min-width:0;max-height:90vh;overflow:auto}
.figview img{max-width:100%;max-height:66vh;object-fit:contain;display:block;
margin:0 auto;background:#fff;border-radius:8px}
.figview figcaption{font-size:.84rem;color:var(--subtext0);margin-top:.7rem;
line-height:1.55}
.fig-nav{background:var(--mantle);border:1px solid var(--surface2);color:var(--text);
border-radius:50%;width:42px;height:42px;font-size:1.25rem;cursor:pointer;flex-shrink:0}
.fig-nav:hover{border-color:var(--primary);color:var(--primary)}
#gpanel{height:calc(100vh - 230px);min-height:560px;border:1px solid var(--surface1);
border-radius:16px;overflow:hidden;background:var(--crust)}
#panel{position:fixed;top:0;right:0;height:100vh;width:min(960px,96vw);
background:var(--mantle);border-left:1px solid var(--surface2);
box-shadow:-12px 0 40px rgba(0,0,0,.28);transform:translateX(103%);
transition:transform .28s ease;z-index:1500;display:flex;flex-direction:column}
#panel.open{transform:none}
main{transition:margin .28s ease}
@media(min-width:1500px){
#panel{width:min(44vw,920px)}
body.panel-open main{margin-right:min(44vw,920px);max-width:none}
}
.panel-head{display:flex;gap:.6rem;align-items:flex-start;justify-content:space-between;
padding:.8rem 1rem .3rem}
.panel-head b{font-family:'Newsreader',Georgia,serif;font-size:1.02rem;line-height:1.35;
font-weight:500}
.panel-meta{padding:0 1rem;font-size:.78rem;color:var(--subtext0)}
.panel-links{display:flex;gap:.45rem;padding:.5rem 1rem .6rem;flex-wrap:wrap}
.panel-body{flex:1;background:var(--crust);display:flex;min-height:0}
.panel-body iframe{flex:1;width:100%;border:0;background:#fff}
.panel-msg{margin:auto;text-align:center;color:var(--subtext0);padding:1.5rem;
line-height:2.4;font-size:.9rem}
.citepop{position:absolute;z-index:1600;background:var(--mantle);
border:1px solid var(--surface2);border-radius:12px;
box-shadow:0 12px 34px rgba(0,0,0,.28);padding:.8rem .95rem;width:min(400px,92vw);
font-family:'Inter',sans-serif;font-size:.82rem;line-height:1.5}
.cp-t{font-family:'Newsreader',Georgia,serif;font-size:.98rem;font-weight:500;
line-height:1.35;margin-bottom:.2rem}
.cp-m{color:var(--subtext0);margin-bottom:.3rem}
.cp-s{color:var(--subtext1);display:-webkit-box;-webkit-line-clamp:4;
-webkit-box-orient:vertical;overflow:hidden;margin-bottom:.55rem}
.cp-b{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.modal-back{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;
align-items:center;justify-content:center;z-index:2000}
.modal{background:var(--mantle);border:1px solid var(--surface2);border-radius:16px;
max-width:600px;width:92%;max-height:82vh;overflow:auto;
box-shadow:0 10px 30px rgba(0,0,0,.45)}
.m-title{font-size:1rem;font-weight:600;color:var(--primary);padding:.7rem 1rem;
background:var(--surface0);border-radius:15px 15px 0 0}
.m-body{padding:1rem}
.m-body pre{background:var(--surface0);border-radius:8px;padding:.6rem;overflow:auto;
max-height:40vh;font-size:.75rem}
.m-btns{display:flex;gap:.5rem;justify-content:flex-end;padding:0 1rem 1rem}
.spinner{width:34px;height:34px;border:4px solid var(--surface1);
border-top-color:var(--primary);border-radius:50%;margin:0 auto .6rem;
animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:760px){
.brand span{display:none}
main{padding:.9rem .9rem 3rem}
.hero{padding:1.1rem 0 .8rem}
.grid{grid-template-columns:1fr}
.ref{flex-direction:column;gap:.5rem}
.ref-side{flex-direction:row;align-items:center;justify-content:flex-end}
#panel{width:100vw}
.trow{grid-template-columns:6rem 1fr 4.5rem}
}
"""
    + GRAPH_CSS
)

_ROLE_JS_COLORS = (
    '{foundational:"#F07898",core:"#B4A2E8",frontier:"#6FC898",'
    'adjacent:"#8B95A8",survey:"#5AB4D8",unrelated:"#FF5370"}'
)
_STAGE_COLORS = (
    '{embed:"#5AB4D8","retrieve+grade":"#B4A2E8","retrieve+grade+rank":"#B4A2E8",'
    '"extract+compose":"#F07898",extract:"#F07898",compose:"#C04868",'
    '"compose-long":"#C04868",judge:"#F0C878",expand:"#8B95A8",critique:"#6FC898",'
    'summaries:"#5AB4D8",figures:"#2A8A60",viz:"#6248B8",pdf:"#a0a0af"}'
)

_THEME_JS = r"""
const de=document.documentElement;
de.dataset.palette=localStorage.getItem('giv-palette')||'haruhana';
de.dataset.mode=localStorage.getItem('giv-mode')||localStorage.getItem('giv-theme')||
  (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
de.dataset.ids=localStorage.getItem('giv-ids')||'off';
function setMode(m){de.dataset.mode=m;localStorage.setItem('giv-mode',m);syncSettings();}
function setPalette(p){de.dataset.palette=p;localStorage.setItem('giv-palette',p);syncSettings();}
function setIds(on){de.dataset.ids=on?'on':'off';
localStorage.setItem('giv-ids',de.dataset.ids);syncSettings();}
function syncSettings(){
  document.querySelectorAll('.swatch').forEach(b=>
    b.classList.toggle('active',b.dataset.p===de.dataset.palette));
  document.querySelectorAll('.mode-btn').forEach(b=>
    b.classList.toggle('active',b.dataset.m===de.dataset.mode));
  const cb=document.getElementById('ids-cb');if(cb)cb.checked=de.dataset.ids==='on';
}
addEventListener('DOMContentLoaded',syncSettings);
document.addEventListener('click',e=>{
  document.querySelectorAll('details.menu[open]').forEach(d=>{
    if(!d.contains(e.target))d.removeAttribute('open');});});
"""

# Shared page JS: escaping, date/duration formatting, stage grouping, and the modal system
# (every action confirms + reports through popups, no alert/notification).
_UI_JS = (
    ("const ROLE_COLORS=" + _ROLE_JS_COLORS + ";")
    + r"""
const GROUP_COLORS={retrieval:'#5AB4D8',reading:'#B4A2E8',writing:'#F07898',judging:'#F0C878'};
const groupOf=s=>s==='judge'?'judging'
  :(s==='embed'||s.indexOf('retrieve')===0||s==='expand')?'retrieval'
  :(s.indexOf('extract')===0||s==='critique'||s==='summaries')?'reading':'writing';
function esc(s){return String(s??'').replace(/[&<>"]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
const ACC={'`':'\u0300',"'":'\u0301','^':'\u0302','~':'\u0303','\"':'\u0308',
  '=':'\u0304','.':'\u0307'};
function deTeX(s){return String(s??'')
  .replace(/\$\\times\$/g,'×')
  .replace(/\$([^$]{0,60}?)\$/g,(m,x)=>x.replace(/\\[a-zA-Z]+/g,'')
    .replace(/[{}^_]/g,''))
  .replace(/\\([`'^~".=])\{?([a-zA-Z])\}?/g,(m,a,c)=>(c+(ACC[a]||''))
    .normalize('NFC'))
  .replace(/\\[a-zA-Z]+\{([^{}]*)\}/g,'$1')
  .replace(/[{}]/g,'');}
function fmt(s){if(s==null)return '—';s=Math.round(s);
  return s>=3600?`${Math.floor(s/3600)}h ${String(Math.floor(s%3600/60)).padStart(2,'0')}m`
    :`${Math.floor(s/60)}m ${String(s%60).padStart(2,'0')}s`;}
function fdate(s){if(!s)return '';const d=new Date(s);if(isNaN(d))return s;
  return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})+
    ', '+d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false});}
function judgeMean(j){
  const v=Object.values(j||{}).filter(x=>typeof x==='number');
  return v.length?(v.reduce((a,b)=>a+b,0)/v.length).toFixed(1):null;}
function groupStages(st){
  const g={};
  for(const[k,v]of Object.entries(st)){
    const G=groupOf(k);
    (g[G]=g[G]||{t:0,parts:[]}).t+=v;
    g[G].parts.push(`${k} ${Math.round(v)}s`);}
  return g;}
function stagebar(st){
  const g=groupStages(st);
  const tot=Object.values(g).reduce((a,b)=>a+b.t,0);
  if(!tot)return '';
  return '<div class="stagebar">'+
    ['retrieval','reading','writing','judging'].filter(k=>g[k]).map(k=>
      `<div style="width:${100*g[k].t/tot}%;background:${GROUP_COLORS[k]}"`+
      ` title="${k} ${Math.round(g[k].t)}s — ${g[k].parts.join(', ')}"></div>`).join('')+
    '</div>';}
function modal(title,body,btns){
  return new Promise(res=>{
    const back=document.createElement('div');back.className='modal-back';
    back.innerHTML=`<div class="modal"><div class="m-title">${esc(title)}</div>`+
      `<div class="m-body">${body}</div><div class="m-btns"></div></div>`;
    const bs=back.querySelector('.m-btns');
    (btns&&btns.length?btns:[{label:'close'}]).forEach(b=>{
      const el=document.createElement('button');
      el.className='pill'+(b.cls?' '+b.cls:'');el.textContent=b.label;
      el.onclick=()=>{back.remove();res(b.value);};bs.appendChild(el);});
    back.addEventListener('click',e=>{if(e.target===back){back.remove();res(undefined);}});
    document.body.appendChild(back);
  });
}
function busy(msg){
  const back=document.createElement('div');back.className='modal-back';
  back.innerHTML=`<div class="modal"><div class="m-body" style="text-align:center">`+
    `<div class="spinner"></div><p class="byline">${esc(msg)}</p></div></div>`;
  document.body.appendChild(back);return back;
}
function resHTML(j){
  if(j.ok){
    const rows=Object.entries(j).filter(([k])=>k!=='ok').map(([k,v])=>
      `<div class="byline"><b>${esc(k)}</b>: `+
      `${esc(typeof v==='object'?JSON.stringify(v):String(v))}</div>`).join('');
    return `<p style="color:var(--tertiary);font-weight:600">✓ done</p>`+rows;
  }
  return `<p style="color:var(--red);font-weight:600">✗ failed</p>`+
    `<div class="byline">${esc(j.error||'unknown error')}</div>`+
    (j.log?`<pre>${esc(j.log)}</pre>`:'');
}
async function act(name,slug,cfg){
  if(name==='delete'){
    const ok=await modal('Delete run',
      `<p>Permanently delete this run and all its artifacts?</p>`+
      `<p class="tech mono">${esc(slug)}/${esc(cfg)}</p>`,
      [{label:'cancel'},{label:'delete',cls:'danger',value:true}]);
    if(!ok)return false;
  }
  const b=busy(name+'…');
  let j;try{j=await(await fetch(`/api/run/${slug}/${cfg}/${name}`,{method:'POST'})).json();}
  catch(e){j={ok:false,error:String(e)};}
  b.remove();
  await modal(name.replace(/-/g,' '),resHTML(j),[{label:'ok',value:true}]);
  return !!j.ok;
}
"""
)


def _swatches() -> str:
    out: list[str] = []
    for pal, modes in _PALETTES.items():
        c1, c2 = modes["light"]["primary"], modes["dark"]["primary"]
        out.append(
            f'<button class="swatch" data-p="{pal}" onclick="setPalette(\'{pal}\')" '
            f'title="{_PALETTE_LABEL[pal]}" '
            f'style="background:linear-gradient(135deg,{c1} 50%,{c2} 50%)"></button>'
        )
    return "".join(out)


def _settings_menu() -> str:
    return f"""<details class="menu">
<summary class="pill" title="appearance &amp; settings">Aa</summary>
<div class="menu-body">
 <div class="m-label">palette</div>
 <div class="mrow">{_swatches()}</div>
 <div class="m-label">mode</div>
 <div class="seg">
  <button class="mode-btn" data-m="light" onclick="setMode('light')">light</button>
  <button class="mode-btn" data-m="dark" onclick="setMode('dark')">dark</button>
 </div>
 <label class="mrow chk"><input type="checkbox" id="ids-cb"
  onchange="setIds(this.checked)"> show technical ids</label>
</div></details>"""


def _page(
    title: str, body: str, head: str = "", script: str = "", public: bool = False
) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{_FONTS}<style>{_CSS}</style>
<script>{_THEME_JS}</script>{head}</head><body{' data-public="on"' if public else ""}>
<nav class="navbar">
<a class="brand" href="/"><b>GraphIV</b><span>Research Library</span></a>
<span class="right">{_settings_menu()}</span></nav>
<main>{body}</main><script>{_UI_JS}{script}</script></body></html>"""


def _scan_runs(out: Path) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    runs: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    if not out.is_dir():
        return runs
    for slug_dir in sorted(out.iterdir()):
        if not slug_dir.is_dir():
            continue
        for cfg_dir in sorted(slug_dir.iterdir()):
            if not cfg_dir.is_dir():
                continue
            rj, pj = cfg_dir / "run.json", cfg_dir / "progress.json"
            if not rj.exists() and not pj.exists():
                continue
            entry: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
                "slug": slug_dir.name,
                "config": cfg_dir.name,
                "question": "",
                "status": "stale",
                "started_at": "",
                "total_seconds": None,
                "stages": {},
                "judge": {},
                "n_landmarks": None,
                "grounded": None,
                "has": {
                    k: (cfg_dir / f).exists()
                    for k, f in (
                        ("report", "report.md"),
                        ("pdf", "report.pdf"),
                        ("graph", "graph.html"),
                        ("papers", "papers.json"),
                        ("tex", "report.tex"),
                    )
                },
            }
            if rj.exists():
                try:
                    meta = json.loads(rj.read_text())  # pyright: ignore[reportAny]
                    entry["status"] = "done"
                    entry["question"] = str(
                        meta.get("question", "")
                    )  # pyright: ignore[reportAny]
                    entry["judge"] = meta.get("judge_scores_final") or {}
                    entry["n_landmarks"] = meta.get("n_landmarks")
                    entry["grounded"] = len(meta.get("grounded") or [])
                    entry["effort"] = meta.get("effort")
                    entry["rounds"] = meta.get("rounds_run")
                    entry["n_figures"] = meta.get("n_figures")
                    roles: dict[str, int] = {}
                    years: list[int] = []
                    for lm in meta.get("landmarks") or []:  # pyright: ignore[reportAny]
                        role = str(
                            lm.get("role") or "ungraded"
                        )  # pyright: ignore[reportAny]
                        roles[role] = roles.get(role, 0) + 1
                        y = lm.get("year")  # pyright: ignore[reportAny]
                        if isinstance(y, int):
                            years.append(y)
                    entry["roles"] = roles
                    entry["years"] = [min(years), max(years)] if years else None
                    tm = meta.get("timings") or {}  # pyright: ignore[reportAny]
                    if isinstance(tm, dict):
                        entry["started_at"] = str(
                            tm.get("started_at", "")
                        )  # pyright: ignore[reportAny]
                        entry["total_seconds"] = tm.get("total_seconds")
                        entry["stages"] = tm.get("stages") or {}
                except Exception:  # noqa: BLE001
                    pass
            elif pj.exists():
                try:
                    prog = json.loads(pj.read_text())  # pyright: ignore[reportAny]
                    entry["question"] = str(
                        prog.get("question", "")
                    )  # pyright: ignore[reportAny]
                    entry["started_at"] = str(
                        prog.get("started_at", "")
                    )  # pyright: ignore[reportAny]
                    entry["total_seconds"] = prog.get("elapsed")
                    stages: dict[str, float] = {}
                    cur = None
                    for s in prog.get("stages") or []:  # pyright: ignore[reportAny]
                        name = str(s.get("name"))  # pyright: ignore[reportAny]
                        sec = s.get("seconds")  # pyright: ignore[reportAny]
                        if isinstance(sec, (int, float)):
                            stages[name] = stages.get(name, 0.0) + float(sec)
                        else:
                            cur = name
                    entry["stages"] = stages
                    entry["current_stage"] = cur
                    import time as _t  # noqa: PLC0415

                    fresh = (_t.time() - pj.stat().st_mtime) < 900
                    entry["status"] = (
                        "running" if (not prog.get("done") and fresh) else "stale"
                    )
                except Exception:  # noqa: BLE001
                    pass
            runs.append(entry)
    runs.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return runs


_INDEX_JS = r"""
const ROLE_ORDER=['foundational','core','frontier','survey','adjacent','unrelated',
  'ungraded'];
function rolebar(roles){
  const rs=ROLE_ORDER.filter(r=>roles&&roles[r]);
  const tot=rs.reduce((a,r)=>a+roles[r],0);
  if(!tot)return '';
  const tip=rs.map(r=>`${roles[r]} ${r}`).join(' · ');
  return `<div class="stagebar" title="${esc(tip)}">`+rs.map(r=>
    `<div style="width:${100*roles[r]/tot}%;background:${ROLE_COLORS[r]||'#a0a0af'}">`+
    `</div>`).join('')+'</div>';
}
function card(r){
  const jm=judgeMean(r.judge);
  const jt=Object.entries(r.judge||{}).map(([k,v])=>`${k} ${v}`).join(' · ');
  const by=[fdate(r.started_at),r.total_seconds!=null?fmt(r.total_seconds):null,
    r.effort?`effort ${r.effort}`:null].filter(Boolean).join(' · ');
  const yr=r.years?(r.years[0]===r.years[1]?String(r.years[0])
    :`${r.years[0]}–${r.years[1]}`):null;
  const facts=[
    r.n_landmarks!=null?`<b>${r.n_landmarks}</b> papers`:null,
    r.grounded?`<b>${r.grounded}</b> cited`:null,
    r.n_figures?`<b>${r.n_figures}</b> figures`:null,
    r.rounds?`<b>${r.rounds}</b> round${r.rounds>1?'s':''}`:null,
    yr?`<b>${yr}</b>`:null,
    jm?`<span title="${esc(jt)}">judge <b>${jm}</b></span>`:null,
  ].filter(Boolean).join('<i>·</i>');
  const status=r.status==='running'
    ?`<div class="live"><span class="dot pulse"></span>${esc(r.current_stage||'running')}…</div>`+
      stagebar(r.stages||{})
    :r.status==='stale'?'<div class="live gray"><span class="dot"></span>interrupted</div>':'';
  return `<article class="card">
    <h3 class="q"><a href="/run/${r.slug}/${r.config}">${esc(r.question||r.slug)}</a></h3>
    <div class="byline">${by}</div>
    <div class="tech mono">${esc(r.slug)} / ${esc(r.config)}</div>
    ${r.status==='done'?`<div class="facts">${facts}</div>${rolebar(r.roles)}`:''}
    ${status}
    <div class="cardfoot">
      ${r.has&&r.has.pdf?`<a class="pill sm" href="/files/${r.slug}/${r.config}/report.pdf" target="_blank">PDF</a>`:''}
      <details class="menu up">
        <summary class="pill sm" title="actions">⋯</summary>
        <div class="menu-body">
          <a class="mi" href="/run/${r.slug}/${r.config}">open</a>
          ${r.has&&r.has.report?`<a class="mi" href="/files/${r.slug}/${r.config}/report.md" target="_blank">report.md</a>`:''}
          <button class="mi danger adminonly" onclick="delRun('${r.slug}','${r.config}')">delete…</button>
        </div>
      </details>
    </div></article>`;
}
let RUNS=[],page=0,per=15,q='';
function render(){
  const f=RUNS.filter(r=>((r.question||'')+' '+r.slug+' '+r.config).toLowerCase().includes(q));
  const pages=Math.max(1,Math.ceil(f.length/per));
  if(page>=pages)page=pages-1;
  document.getElementById('grid').innerHTML=
    f.slice(page*per,page*per+per).map(card).join('')||
    '<p class="byline">no matching research</p>';
  document.getElementById('pager').innerHTML=
    `<button class="pill sm" ${page===0?'disabled':''} onclick="go(-1)">‹</button>`+
    `<span>${page+1} / ${pages}</span>`+
    `<button class="pill sm" ${page>=pages-1?'disabled':''} onclick="go(1)">›</button>`;
  const running=RUNS.filter(r=>r.status==='running').length;
  document.getElementById('count').textContent=
    `${RUNS.length} research report${RUNS.length===1?'':'s'}`+
    (running?` · ${running} in progress`:'');
}
function go(d){page+=d;render();}
async function delRun(s,c){
  if(await act('delete',s,c)){RUNS=RUNS.filter(r=>!(r.slug===s&&r.config===c));render();}
}
async function tick(){
  try{RUNS=await(await fetch('/api/runs')).json();}catch(e){}
  render();
  setTimeout(tick,RUNS.some(r=>r.status==='running')?5000:60000);
}
document.getElementById('q').addEventListener('input',e=>{
  q=e.target.value.toLowerCase();page=0;render();});
document.getElementById('per').addEventListener('change',e=>{
  per=+e.target.value;page=0;render();});
tick();
"""


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
    return _page("GraphIV — Research Library", body, script=_INDEX_JS, public=public)


_RUN_JS = r"""
const SLUG=__SLUG__,CFG=__CFG__,BASE=`/files/${SLUG}/${CFG}`;
const STAGE_COLORS=__STAGES__;
const TABS=['report','references','graph','figures','details'];
let RUN=null,PAPERS=[],PMAP={},CITED=new Set(),graphDone=false;
let papersResolve;const papersReady=new Promise(r=>papersResolve=r);
function tab(n){
  if(!TABS.includes(n))n='report';
  document.querySelectorAll('.tab-panel').forEach(p=>
    p.classList.toggle('active',p.id==='p-'+n));
  document.querySelectorAll('.tabs button').forEach(b=>
    b.classList.toggle('active',b.dataset.t===n));
  localStorage.setItem('giv-tab-'+SLUG,n);
  if(n==='graph')ensureGraph();
}
async function jfetch(f){try{const r=await fetch(BASE+'/'+f);
  return r.ok?await r.json():null;}catch(e){return null;}}
async function tfetch(f){try{const r=await fetch(BASE+'/'+f);
  return r.ok?await r.text():null;}catch(e){return null;}}
function rolechip(r){return r?`<span class="rolechip" `+
  `style="background:${ROLE_COLORS[r]||'#a0a0af'}">${r}</span>`:'';}
function authorsShort(a){
  if(!a)return '';
  const parts=deTeX(a).split(/,\s*|\s+and\s+/).filter(Boolean);
  return parts.length>3?parts.slice(0,3).join(', ')+' et al.':parts.join(', ');
}
function fixRelUrls(el){
  el.querySelectorAll('img').forEach(i=>{
    const s=i.getAttribute('src');
    if(s&&!/^(https?:)?\//.test(s))i.src=BASE+'/'+s;});
  el.querySelectorAll('a').forEach(a=>{
    const h=a.getAttribute('href');
    if(h&&!/^(https?:)?\//.test(h)&&!h.startsWith('#')&&!h.startsWith('mailto:'))
      a.href=BASE+'/'+h;});
}
// ---- pdf slide-over panel -------------------------------------------------
async function openPanel(o){
  const P=document.getElementById('panel');P.classList.add('open');
  document.body.classList.add('panel-open');
  document.getElementById('panel-t').textContent=o.title||'';
  document.getElementById('panel-m').innerHTML=o.meta||'';
  document.getElementById('panel-l').innerHTML=
    (o.ext?`<a class="pill sm" target="_blank" href="${o.ext}">arXiv ↗</a>`:'')+
    `<a class="pill sm" target="_blank" href="${o.url}">open in tab ↗</a>`;
  const b=document.getElementById('panel-b');
  b.innerHTML='<div class="panel-msg"><div class="spinner"></div></div>';
  let ok=false;try{ok=(await fetch(o.url,{method:'HEAD'})).ok;}catch(e){}
  if(ok){b.innerHTML=`<iframe src="${o.url}"></iframe>`;return;}
  if(o.fetchUrl){
    b.innerHTML='<div class="panel-msg">not in the local store<br>'+
      '<button class="pill sm" id="pfetch">fetch from arXiv (~10s)</button></div>';
    document.getElementById('pfetch').onclick=async ev=>{
      ev.target.textContent='fetching…';ev.target.disabled=true;
      let got=false;try{got=(await fetch(o.fetchUrl,{method:'HEAD'})).ok;}catch(e){}
      b.innerHTML=got?`<iframe src="${o.url}"></iframe>`
        :'<div class="panel-msg">arXiv fetch failed — use the arXiv link above</div>';};
  }else if(o.compile){
    b.innerHTML='<div class="panel-msg"><div class="spinner"></div>'+
      'compiling report.tex → pdf (latexmk)…</div>';
    let j=null;
    try{j=await(await fetch(`/api/run/${SLUG}/${CFG}/compile-pdf`,
      {method:'POST'})).json();}catch(e){}
    b.innerHTML=j&&j.ok?`<iframe src="${o.url}"></iframe>`
      :`<div class="panel-msg">could not compile a PDF`+
       `${j&&j.error?'<br><span class="tech mono">'+esc(j.error)+'</span>':''}</div>`;
  }else b.innerHTML='<div class="panel-msg">not available</div>';
}
function closePanel(){document.getElementById('panel').classList.remove('open');
  document.body.classList.remove('panel-open');}
function openPaper(id){
  hidePop();
  const p=PMAP[id];
  openPanel({title:p?deTeX(p.title):('arXiv:'+id),
    meta:p?esc([authorsShort(p.authors),p.year,id].filter(Boolean).join(' · ')):esc(id),
    url:'/pdf/'+id,fetchUrl:'/pdf/'+id+'?fetch=1',
    ext:'https://arxiv.org/abs/'+id});
}
function openReportPdf(){
  openPanel({title:RUN&&RUN.question?RUN.question:'report.pdf',
    meta:'compiled literature review',
    url:BASE+'/report.pdf',ext:BASE+'/report.pdf',compile:true});
}
// ---- citation hover previews ----------------------------------------------
let popEl=null,popTimer=null;
function hidePop(){if(popEl){popEl.remove();popEl=null;}}
function hidePopSoon(){popTimer=setTimeout(hidePop,250);}
function showPop(a,id){
  clearTimeout(popTimer);hidePop();
  const p=PMAP[id];
  popEl=document.createElement('div');popEl.className='citepop';
  const btns=`<div class="cp-b">`+
    `<button class="pill sm" onclick="openPaper('${id}')">Read PDF</button>`+
    `<a class="pill sm" target="_blank" href="https://arxiv.org/abs/${id}">arXiv ↗</a>`+
    `<span class="tech mono">${esc(id)}</span></div>`;
  popEl.innerHTML=p?`<div class="cp-t">${esc(deTeX(p.title))}</div>`+
    `<div class="cp-m">${esc(authorsShort(p.authors))}${p.authors?' · ':''}`+
    `${p.year??''} ${rolechip(p.role)}</div>`+
    (p.summary?`<div class="cp-s">${esc(deTeX(p.summary))}</div>`:'')+btns
   :`<div class="cp-m mono">arXiv:${esc(id)}</div>`+btns;
  const r=a.getBoundingClientRect();
  popEl.style.left=Math.min(r.left+scrollX,scrollX+innerWidth-420)+'px';
  popEl.style.top=(r.bottom+scrollY+6)+'px';
  popEl.addEventListener('mouseenter',()=>clearTimeout(popTimer));
  popEl.addEventListener('mouseleave',hidePopSoon);
  document.body.appendChild(popEl);
}
const AID=/arxiv\.org\/abs\/([\w.\/-]+?)(?:v\d+)?$/;
function hookCitations(el){
  el.querySelectorAll('a[href*="arxiv.org/abs/"]').forEach(a=>{
    const m=(a.getAttribute('href')||'').match(AID);if(!m)return;
    const id=m[1];
    a.addEventListener('click',e=>{
      if(e.ctrlKey||e.metaKey)return;e.preventDefault();openPaper(id);});
    a.addEventListener('mouseenter',()=>showPop(a,id));
    a.addEventListener('mouseleave',hidePopSoon);
  });
}
// ---- loading ----------------------------------------------------------------
async function load(){
  const run=await jfetch('run.json');
  if(!run){papersResolve();await showProgress();return;}
  RUN=run;
  const qt=run.question||SLUG;
  document.getElementById('qtitle').textContent=qt;
  document.title='GraphIV — '+qt;
  (run.grounded||[]).forEach(id=>CITED.add(id));
  const papers=await jfetch('papers.json');
  PAPERS=papers||[];PAPERS.forEach(p=>{PMAP[p.arxiv_id]=p;});
  papersResolve();
  const tm=run.timings||{};
  const jm=judgeMean(run.judge_scores_final);
  document.getElementById('rbyline').textContent=[
    fdate(tm.started_at),tm.total_seconds!=null?fmt(tm.total_seconds):null,
    PAPERS.length?`${PAPERS.length} papers`:null,
    CITED.size?`${CITED.size} cited`:null,
    jm?`judge ${jm}`:null,
    run.effort?`effort ${run.effort}`:null].filter(Boolean).join(' · ');
  const md=await tfetch('report.md');
  const rel=document.getElementById('report-md');
  if(md){rel.innerHTML=marked.parse(md);fixRelUrls(rel);hookCitations(rel);
    if(window.Prism)Prism.highlightAllUnder(rel);}
  else rel.innerHTML='<p class="byline">no report.md in this run</p>';
  renderRefs();
  renderFigs(run);
  renderDetails(run,await jfetch('judge_transcript.json'));
}
async function showProgress(){
  const pr=await jfetch('progress.json');
  const el=document.getElementById('report-md');
  if(!pr){el.innerHTML='<p class="byline">no artifacts found for this run</p>';return;}
  const qt=pr.question||SLUG;
  document.getElementById('qtitle').textContent=qt;document.title='GraphIV — '+qt;
  const stages=pr.stages||[];
  const done=stages.filter(s=>typeof s.seconds==='number');
  const cur=stages.find(s=>s.seconds==null);
  const max=Math.max(...done.map(s=>s.seconds),1);
  el.innerHTML=`<div style="text-align:center;padding:1.6rem 0 1rem">
    <div class="spinner"></div>
    <p style="margin:.5rem 0">research in progress`+
    `${cur?` — <b>${esc(cur.name)}</b>`:''}</p>
    <p class="byline">${fmt(pr.elapsed)} elapsed · ${done.length} stages complete</p>
    </div><div style="font-family:'Inter',sans-serif;max-width:560px;margin:0 auto">`+
    done.map(s=>`<div class="trow"><span>${esc(s.name)}</span>
      <div class="tbar"><div style="width:${100*s.seconds/max}%;`+
      `background:${STAGE_COLORS[s.name]||'#8B95A8'}"></div></div>
      <span class="mono">${Math.round(s.seconds)}s</span></div>`).join('')+'</div>';
  setTimeout(async()=>{
    const r=await jfetch('run.json');
    if(r)location.reload();else showProgress();},5000);
}
// ---- references (summaries of every referenced text) ------------------------
let refFilter='all',refSort='relevance',refQ='';
function refItem(p){
  const cited=CITED.has(p.arxiv_id);
  const meta=[authorsShort(p.authors),p.year,p.category].filter(Boolean).join(' · ');
  return `<div class="ref">
   <div class="ref-main">
    <div class="ref-t"><a href="#" onclick="openPaper('${p.arxiv_id}');return false">`+
     `${esc(deTeX(p.title))}</a>${cited?'<span class="cited-b">CITED</span>':''}</div>
    <div class="ref-m">${esc(meta)} ${rolechip(p.role)}</div>
    <div class="tech mono">${esc(p.arxiv_id)} · rel ${p.relevance??'?'} · `+
     `cos ${p.cosine??'?'} · in-degree ${p.in_degree??'?'}</div>
    ${p.summary||p.reason?`<p class="ref-s">${esc(deTeX(p.summary||p.reason))}</p>`:''}
   </div>
   <div class="ref-side">
    <button class="pill sm" onclick="openPaper('${p.arxiv_id}')">PDF</button>
    <a class="pill sm" target="_blank" href="${p.url||('https://arxiv.org/abs/'+p.arxiv_id)}">arXiv ↗</a>
   </div></div>`;
}
function renderRefs(){
  const host=document.getElementById('refs');
  if(!PAPERS.length){
    host.innerHTML='<p class="byline">no reference summaries in this run</p>';return;}
  if(!document.getElementById('reflist')){
    host.innerHTML=`<div class="rtools">
      <input type="search" id="rq" placeholder="filter references…">
      <select class="pill sm" id="rfilter">
       <option value="all">all papers</option>
       <option value="cited">cited in report</option>
       <option value="uncited">not cited</option></select>
      <select class="pill sm" id="rsort">
       <option value="relevance">by relevance</option>
       <option value="year">by year</option>
       <option value="in_degree">by citations</option>
       <option value="cosine">by similarity</option></select>
      <span class="byline" id="rcount"></span></div>
     <div class="reflist" id="reflist"></div>`;
    document.getElementById('rq').addEventListener('input',e=>{
      refQ=e.target.value.toLowerCase();renderRefs();});
    document.getElementById('rfilter').addEventListener('change',e=>{
      refFilter=e.target.value;renderRefs();});
    document.getElementById('rsort').addEventListener('change',e=>{
      refSort=e.target.value;renderRefs();});
  }
  let ps=PAPERS.filter(p=>
    refFilter==='all'||(refFilter==='cited')===CITED.has(p.arxiv_id));
  if(refQ)ps=ps.filter(p=>
    ((p.title||'')+' '+(p.authors||'')+' '+(p.summary||'')+' '+p.arxiv_id)
    .toLowerCase().includes(refQ));
  ps=[...ps].sort((a,b)=>{
    if(refSort==='relevance')
      return (b.relevance??-9)-(a.relevance??-9)||(b.cosine??0)-(a.cosine??0);
    return (b[refSort]??-1e9)-(a[refSort]??-1e9);});
  document.getElementById('rcount').textContent=
    `${ps.length} of ${PAPERS.length} · `+
    `${PAPERS.filter(p=>CITED.has(p.arxiv_id)).length} cited in the report`;
  document.getElementById('reflist').innerHTML=
    ps.map(refItem).join('')||'<p class="byline">nothing matches</p>';
}
// ---- graph / figures / details ----------------------------------------------
async function ensureGraph(){
  if(graphDone)return;graphDone=true;
  const el=document.getElementById('gpanel');
  await papersReady;
  let d=null;
  try{const r=await fetch(`/api/run/${SLUG}/${CFG}/graph-data`);
    if(r.ok)d=await r.json();}catch(e){}
  if(!d){el.innerHTML='<p class="byline" style="padding:1rem">no graph for this run</p>';
    return;}
  d.nodes.forEach(n=>{const p=PMAP[n.id];
    if(n.title)n.title=deTeX(n.title);
    if(p){if(p.summary)n.summary=deTeX(p.summary);
      if(p.authors)n.authors=authorsShort(p.authors);
      if(!n.title&&p.title)n.title=deTeX(p.title);}});
  renderStoryGraph(el,d,'/pdf',n=>openPaper(n.id));
}
let FIGS=[],figIdx=0;
function renderFigs(run){
  FIGS=run&&run.figures?Object.entries(run.figures):[];
  document.getElementById('figgrid').innerHTML=FIGS.map(([id,f],i)=>
    `<img class="fig-th" src="${BASE}/${f.file}" loading="lazy" onclick="openFig(${i})"
      title="${esc(PMAP[id]?deTeX(PMAP[id].title):id)}">`
  ).join('')||'<p class="byline">no figures in this run</p>';
}
function closeFig(){const b=document.getElementById('figbox');if(b)b.remove();}
function openFig(i){
  if(!FIGS.length)return;
  figIdx=((i%FIGS.length)+FIGS.length)%FIGS.length;
  const[id,f]=FIGS[figIdx];
  let box=document.getElementById('figbox');
  if(!box){box=document.createElement('div');box.id='figbox';box.className='modal-back';
    box.addEventListener('click',e=>{if(e.target===box)box.remove();});
    document.body.appendChild(box);}
  box.innerHTML=`<div class="figview">
    <button class="fig-nav" onclick="openFig(figIdx-1)">‹</button>
    <figure><img src="${BASE}/${f.file}">
     <figcaption><b>${esc(PMAP[id]?deTeX(PMAP[id].title):id)}</b> · p.${f.page}
      <span class="tech mono">· ${esc(id)}</span><br>${esc(deTeX(f.caption||''))}
      <div class="cp-b" style="margin-top:.6rem">
       <button class="pill sm" onclick="closeFig();openPaper('${id}')">Read paper</button>
       <span class="byline">${figIdx+1} / ${FIGS.length}</span>
      </div></figcaption></figure>
    <button class="fig-nav" onclick="openFig(figIdx+1)">›</button></div>`;
}
function renderDetails(run,jt){
  document.getElementById('details').innerHTML=
   `<div class="section"><h2>Timings</h2><div id="timings"></div></div>
    <div class="section"><h2>Judge</h2><div id="judge"></div></div>
    <div class="section tech"><h2>Metadata</h2><pre id="runmeta" class="mono"></pre></div>`;
  renderTimings(run);
  renderJudge(jt||[]);
  document.getElementById('runmeta').textContent=JSON.stringify(
    Object.fromEntries(Object.entries(run).filter(([k])=>
      !['landmarks','figures','grounded','off_digest','schema'].includes(k))),null,1);
}
function renderTimings(run){
  const tm=run.timings||{};const st=tm.stages||{};
  const entries=Object.entries(st);
  if(!entries.length){
    document.getElementById('timings').innerHTML='<p class="byline">no timings</p>';return;}
  const tot=entries.reduce((a,[,v])=>a+v,0)||1;
  const groups={};
  entries.forEach(([k,v])=>{const g=groupOf(k);(groups[g]=groups[g]||[]).push([k,v]);});
  const order=['retrieval','reading','writing','judging'].filter(g=>groups[g]);
  const chips=`<div class="stats">
    <div class="stat"><b>${fmt(tm.total_seconds)}</b>total</div>
    ${order.map(g=>{
      const t=groups[g].reduce((a,[,v])=>a+v,0);
      return `<div class="stat"><b style="color:${GROUP_COLORS[g]}">${fmt(t)}</b>`+
        `${g} · ${Math.round(100*t/tot)}%</div>`;}).join('')}
  </div>
  <p class="byline">started ${esc(tm.started_at||'?')} · finished ${esc(tm.finished_at||'?')}</p>`;
  const max=Math.max(...entries.map(([,v])=>v),1);
  const bars=order.map(g=>
    `<h3 style="color:${GROUP_COLORS[g]};font-size:.95rem;margin:.9rem 0 .2rem">${g}</h3>`+
    groups[g].sort((a,b)=>b[1]-a[1]).map(([k,v])=>
      `<div class="trow"><span>${esc(k)}</span>
        <div class="tbar"><div style="width:${100*v/max}%;`+
        `background:${STAGE_COLORS[k]||GROUP_COLORS[g]}"></div></div>
        <span class="mono">${Math.round(v)}s · ${Math.round(100*v/tot)}%</span></div>`).join('')
  ).join('');
  document.getElementById('timings').innerHTML=chips+bars;
}
function renderJudge(jt){
  if(!jt.length){document.getElementById('judge').innerHTML=
    '<p class="byline">single-pass run (no judge transcript)</p>';return;}
  const axes=Object.keys(jt[0].scores||{});
  document.getElementById('judge').innerHTML=
   `<table><tr><th>round</th>${axes.map(a=>`<th>${a}</th>`).join('')}`+
   `<th>saturated</th><th>gaps / assessment</th></tr>`+
   jt.map(r=>`<tr><td>${r.round}</td>`+
    `${axes.map(a=>`<td>${(r.scores||{})[a]??''}</td>`).join('')}
    <td>${r.saturated?'✔':''}</td>
    <td>${(r.gaps||[]).map(esc).join('; ')}<br>`+
    `<i class="byline">${esc(r.assessment||'')}</i></td></tr>`).join('')+'</table>';
}
async function actRun(name){
  const ok=await act(name,SLUG,CFG);
  if(ok&&name==='delete')location.href='/';
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if(document.getElementById('figbox')){closeFig();return;}
    closePanel();hidePop();return;}
  if(document.getElementById('figbox')){
    if(e.key==='ArrowRight')openFig(figIdx+1);
    if(e.key==='ArrowLeft')openFig(figIdx-1);}});
load();
tab(localStorage.getItem('giv-tab-'+SLUG)||'report');
"""


def _run_html(slug: str, cfg: str, question: str = "", public: bool = False) -> str:
    tabs = (
        ("report", "Report"),
        ("references", "References"),
        ("graph", "Graph"),
        ("figures", "Figures"),
        ("details", "Details"),
    )
    tab_btns = "".join(
        f'<button data-t="{t}" onclick="tab(\'{t}\')">{label}</button>'
        for t, label in tabs
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
  <details class="menu adminonly"><summary class="ab-btn" title="run actions">&ctdot;</summary>
   <div class="menu-body">
    <button class="mi" onclick="actRun('purge-cache')">Purge caches</button>
    <button class="mi danger" onclick="actRun('delete')">Delete run&hellip;</button>
   </div></details>
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
    )
    title = f"GraphIV — {html_mod.escape(question) if question else slug}"
    return _page(title, body, head=head, script=GRAPH_JS + "\n" + run_js, public=public)


def _purge_caches(question: str) -> dict[str, int]:
    """Delete this question's grade + critique cache rows (extract/summary stay: shared)."""
    qhash = hashlib.sha1(question.encode()).hexdigest()[:12]
    out: dict[str, int] = {}
    for name, db, table in (
        ("grades", _GRADE_DB, "grade"),
        ("critiques", _CRIT_DB, "critique"),
    ):
        n = 0
        if db.exists():
            conn = sqlite3.connect(db)
            try:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE qhash=?", (qhash,)
                )  # noqa: S608
                n = cur.rowcount
                conn.commit()
            except sqlite3.OperationalError:
                pass
            conn.close()
        out[name] = n
    return out


_DATA_RE = re.compile(r"const DATA = (\{.*\});")


def _run_question(d: Path) -> str:
    for f in ("run.json", "progress.json"):
        p = d / f
        if p.exists():
            try:
                return str(
                    json.loads(p.read_text()).get("question", "")
                )  # pyright: ignore[reportAny]
            except Exception:  # noqa: BLE001
                pass
    return ""


def register(mcp: FastMCP, out: Path) -> None:
    """Attach dashboard + action routes to the FastMCP starlette app (http transport)."""
    from starlette.responses import (  # noqa: PLC0415
        HTMLResponse,
        JSONResponse,
        Response as StarletteResponse,
    )

    def _cfg_dir(request: Request) -> Path | None:
        slug = str(request.path_params["slug"])  # pyright: ignore[reportAny]
        cfg = str(request.path_params["cfg"])  # pyright: ignore[reportAny]
        d = (out / slug / cfg).resolve()
        if not str(d).startswith(str(out.resolve()) + "/") or not d.is_dir():
            return None
        return d

    def _is_public(request: Request) -> bool:
        # Set by caddy on the gated cloudflared vhost (see nixos-configs graphiv.nix);
        # cosmetic only — the 403s on the closed endpoints are enforced by caddy.
        return request.headers.get("x-graphiv-public") is not None

    @mcp.custom_route("/", methods=["GET"])
    async def index(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        return HTMLResponse(_index_html(_is_public(request)))

    @mcp.custom_route("/api/runs", methods=["GET"])
    async def api_runs(_: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(_scan_runs(out))

    @mcp.custom_route("/run/{slug}/{cfg}", methods=["GET"])
    async def run_page(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return HTMLResponse("<h1>run not found</h1>", status_code=404)
        return HTMLResponse(
            _run_html(d.parent.name, d.name, _run_question(d), _is_public(request))
        )

    @mcp.custom_route("/api/run/{slug}/{cfg}/graph-data", methods=["GET"])
    async def run_graph_data(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        """The embedded DATA json out of graph.html — lets the dashboard render the
        interactive graph (with the pdf sidebar) for runs generated before this UI."""
        d = _cfg_dir(request)
        if d is None or not (d / "graph.html").exists():
            return JSONResponse({"error": "no graph"}, status_code=404)
        m = _DATA_RE.search((d / "graph.html").read_text(encoding="utf-8"))
        if m is None:
            return JSONResponse({"error": "no DATA in graph.html"}, status_code=404)
        return StarletteResponse(m.group(1), media_type="application/json")

    @mcp.custom_route("/api/run/{slug}/{cfg}/delete", methods=["POST"])
    async def run_delete(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        await asyncio.to_thread(shutil.rmtree, d)
        if not any(d.parent.iterdir()):
            d.parent.rmdir()
        return JSONResponse({"ok": True, "deleted": f"{d.parent.name}/{d.name}"})

    @mcp.custom_route("/api/run/{slug}/{cfg}/purge-cache", methods=["POST"])
    async def run_purge(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        question = _run_question(d)
        if not question:
            return JSONResponse({"ok": False, "error": "no question in run meta"})
        return JSONResponse({"ok": True, "purged": _purge_caches(question)})

    @mcp.custom_route("/api/run/{slug}/{cfg}/compile-pdf", methods=["POST"])
    async def run_pdf(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        if not (d / "report.tex").exists():
            return JSONResponse(
                {"ok": False, "error": "no report.tex (single-pass run)"}
            )
        # async subprocess: a blocking run here stalls FastMCP keepalives (event loop).
        try:
            proc = await asyncio.create_subprocess_exec(
                "latexmk",
                "-pdf",
                "-g",
                "-interaction=nonstopmode",
                "report.tex",
                cwd=d,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            return JSONResponse(
                {"ok": False, "error": "latexmk not on PATH (run in the dev shell)"}
            )
        try:
            out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        except TimeoutError:
            proc.kill()
            return JSONResponse({"ok": False, "error": "latexmk timed out (600s)"})
        ok = proc.returncode == 0 and (d / "report.pdf").exists()
        if not ok:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"latexmk exit {proc.returncode}",
                    "log": out_b.decode(errors="replace")[-3000:],
                }
            )
        return JSONResponse(
            {"ok": True, "pdf": f"/files/{d.parent.name}/{d.name}/report.pdf"}
        )
