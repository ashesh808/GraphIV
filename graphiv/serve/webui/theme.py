"""
The four shunka-shuutou palettes, the stylesheet and the palette picker

Colors mirror kkuroma.github.io themes.js, so the dashboard and the site stay one design.
"""

from __future__ import annotations

from graphiv.generate.graph_viz import GRAPH_CSS

# The four shunka-shuutou palettes from kkuroma.github.io themes.js (subset of vars used here)
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
