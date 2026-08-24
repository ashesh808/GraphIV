"""
The stylesheet, in the dashboard's idiom: the same variable names, fonts and pill controls

Only the haruhana palette ships here, since a labeling session is not a place to pick a theme
"""

from __future__ import annotations

_FONTS: str = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    "?family=Newsreader:ital,opsz,wght@0,6..72,400..700;1,6..72,400..700"
    "&family=Inter:wght@400;500;600;700"
    '&family=JetBrains+Mono:wght@400;500&display=swap">'
)

_PALETTE: str = """
:root,[data-mode="light"]{--base:#EFF0F8;--mantle:#FFFFFF;--crust:#e1e2ed;--text:#252535;
--subtext1:#393947;--subtext0:#565662;--surface2:#C8C8D8;--surface1:#d4d4e2;--surface0:#dddeea;
--overlay1:#848491;--overlay0:#a0a0af;--primary:#C04868;--secondary:#6248B8;--tertiary:#2A8A60;
--red:#B00020;--yellow:#8A6A00;--green:#2A8A60;--sky:#1E7AA8;--hilite:#F8D06A}
[data-mode="dark"]{--base:#0C0F1E;--mantle:#171D36;--crust:#090B15;--text:#D4D0EA;
--subtext1:#babbd3;--subtext0:#8B95A8;--surface2:#424D68;--surface1:#2B3758;--surface0:#232E4C;
--overlay1:#6a758b;--overlay0:#58637b;--primary:#F07898;--secondary:#B4A2E8;--tertiary:#6FC898;
--red:#FF5370;--yellow:#F8D06A;--green:#6FC898;--sky:#8AD4F0;--hilite:#8A6A00}
"""

_CSS: str = (
    _PALETTE
    + """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Noto Sans',-apple-system,'Segoe UI',sans-serif;
background:var(--base);color:var(--text);line-height:1.6;font-size:15px;
-webkit-font-smoothing:antialiased;overflow:hidden}
h1,h2,h3,.q{font-family:'Newsreader',Georgia,serif;font-weight:600}
code,.mono{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.86em}
a{color:var(--primary);text-decoration:none}
a:hover{border-bottom:1px dotted var(--primary)}
.navbar{display:flex;align-items:center;justify-content:space-between;gap:.75rem;
padding:.55rem clamp(.9rem,3vw,1.6rem);background:var(--mantle);
border-bottom:1px solid var(--surface1);height:52px}
.brand{display:flex;align-items:baseline;gap:.6rem;color:var(--text)}
.brand b{font-family:'Newsreader',Georgia,serif;font-size:1.3rem;font-weight:600}
.brand span{font-size:.78rem;color:var(--subtext0);letter-spacing:.5px}
.navbar .right{display:flex;gap:.6rem;align-items:center}
.pill{border:1px solid var(--surface2);border-radius:9999px;font-family:inherit;
font-size:.85rem;color:var(--text);background:var(--mantle);padding:.34rem .9rem;
cursor:pointer;transition:all .18s;line-height:1.45}
.pill:hover{background:var(--surface0);border-color:var(--overlay0)}
.pill:disabled{opacity:.4;cursor:default}
.pill.sm{font-size:.75rem;padding:.18rem .6rem}
.counts{font-size:.82rem;color:var(--subtext0)}
.counts b{color:var(--text)}
#bar{height:3px;background:var(--surface1)}
#bar div{height:100%;background:var(--primary);transition:width .25s}
.split{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(430px,1fr);
height:calc(100vh - 55px)}
.pane{overflow:auto;padding:1rem clamp(.8rem,2vw,1.4rem) 3rem}
.pane.pdf{background:var(--crust);border-right:1px solid var(--surface1);text-align:center}
.pdfhead{display:flex;justify-content:space-between;align-items:center;gap:.6rem;
margin-bottom:.7rem;font-size:.8rem;color:var(--subtext0)}
#page{max-width:100%;border-radius:8px;box-shadow:0 6px 26px rgba(0,0,0,.22);
background:#fff;display:block;margin:0 auto}
.miss{padding:3rem 1rem;color:var(--subtext0);font-size:.9rem}
.card{background:var(--mantle);border:1px solid var(--surface1);border-radius:14px;
padding:.95rem 1.1rem;margin-bottom:.85rem}
.card h3{font-size:.72rem;letter-spacing:.8px;text-transform:uppercase;
color:var(--overlay1);font-family:'Inter',sans-serif;font-weight:600;margin-bottom:.5rem}
.sentence{font-family:'Newsreader',Georgia,serif;font-size:1.12rem;line-height:1.6}
.sentence mark{background:var(--hilite);color:inherit;border-radius:3px;padding:0 .12em}
.meta{font-size:.8rem;color:var(--subtext0);margin-top:.5rem}
.meta b{color:var(--text);font-weight:600}
.ptitle{font-family:'Newsreader',Georgia,serif;font-size:1.02rem;line-height:1.4;
font-weight:600;margin-bottom:.25rem}
.authors{font-size:.79rem;color:var(--subtext0);line-height:1.45}
.abs{font-size:.82rem;color:var(--subtext1);margin-top:.5rem;max-height:6.4rem;
overflow:auto;line-height:1.55}
.axes{position:sticky;bottom:0;background:var(--mantle);border:1px solid var(--surface1);
border-radius:14px;padding:.85rem 1rem}
.axis{margin-bottom:.6rem}
.axis:last-child{margin-bottom:0}
.axis h4{font-size:.68rem;letter-spacing:.8px;text-transform:uppercase;
color:var(--overlay1);margin-bottom:.35rem;font-weight:600}
.opts{display:flex;flex-wrap:wrap;gap:.35rem}
.opt{display:flex;align-items:center;gap:.4rem;border:1px solid var(--surface2);
border-radius:9999px;padding:.24rem .7rem;font-size:.84rem;cursor:pointer;
background:var(--mantle);transition:all .15s}
.opt:hover{background:var(--surface0)}
.opt.sel{background:var(--primary);border-color:var(--primary);color:var(--mantle)}
.opt.hint{border-color:var(--secondary);border-style:dashed}
.opt.hint.sel{border-style:solid}
[data-hint="off"] .opt.hint{border-color:var(--surface2);border-style:solid}
[data-hint="off"] #guess{display:none}
#guess{font-size:.72rem;color:var(--secondary);margin-top:.4rem}
#guess b{font-weight:600}
.opt kbd{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.72rem;
background:var(--surface1);border-radius:4px;padding:0 .3rem;color:var(--subtext0)}
.opt.sel kbd{background:rgba(255,255,255,.25);color:var(--mantle)}
.hint{font-size:.72rem;color:var(--overlay1);margin-top:.55rem}
.hint kbd{font-family:'JetBrains Mono',ui-monospace,monospace;background:var(--surface1);
border-radius:4px;padding:0 .3rem}
#fin{text-align:center;padding:4rem 1rem;font-size:1.2rem;color:var(--subtext0)}
"""
)
