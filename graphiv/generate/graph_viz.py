"""
Render the story graph twice from one layout: a static PNG and an interactive page

Position is deterministic, with publication month on x and cosine to the query on y
The HTML render is self-contained, so a run directory reads correctly on its own
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.generate.story import Story

# Haruhana (dark) role colors; connector/ungraded stay chrome-gray
ROLE_COLOR: dict[str, str] = {
    "foundational": "#F07898",
    "core": "#B4A2E8",
    "frontier": "#6FC898",
    "adjacent": "#8B95A8",
    "survey": "#5AB4D8",
    "unrelated": "#FF5370",
}
CONNECTOR_COLOR = "#58637b"
EDGE_COLOR = "#2B3758"
THREAD_COLOR = "#F0C878"


@dataclass
class VizNode:
    """
    One plotted paper, positioned by publication time and cosine to the query
    """

    id: str
    year: int | None
    t: float | None
    title: str
    role: str | None
    relevance: int | None
    in_degree: int
    score: float
    connector: bool
    color: str


@dataclass
class VizEdge:
    """
    One plotted citation, flagged when it belongs to a story thread
    """

    src: str
    dst: str
    intent: str | None
    thread: bool


# YYMM prefix of both modern (2401.12345) and legacy (hep-th/9901001) ids
_ID_YYMM = re.compile(r"^(?:[a-z-]+(?:\.[A-Z]{2})?/)?(\d{2})(\d{2})")


def _time_of(arxiv_id: str, year: int | None) -> float | None:
    """
    Month-resolved publication time from the id's YYMM prefix; falls back to year
    """
    m = _ID_YYMM.match(arxiv_id)
    if m:
        yy, mm = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12:
            yr = 1900 + yy if yy >= 90 else 2000 + yy
            return yr + (mm - 1) / 12.0
    return float(year) if year is not None else None


def _viz_nodes_edges(
    landmarks: list[Landmark],
    edges: list[Edge],
    story: Story,
    pool: dict[str, PoolNode],
) -> tuple[list[VizNode], list[VizEdge]]:
    lm_by_id = {lm.arxiv_id: lm for lm in landmarks}
    conn_ids = [a for a in story.connectors if a not in lm_by_id and a in pool]
    keep = set(lm_by_id) | set(conn_ids)
    thread_steps: set[tuple[str, str]] = set()
    for chain in story.threads:
        for a, b in zip(
            chain, chain[1:], strict=False
        ):  # oldest -> newest; citation edge is b -> a
            thread_steps.add((b, a))

    nodes: list[VizNode] = [
        VizNode(
            id=lm.arxiv_id,
            year=lm.year,
            t=_time_of(lm.arxiv_id, lm.year),
            title=lm.title,
            role=lm.role,
            relevance=lm.relevance,
            in_degree=lm.in_degree,
            score=round(lm.score, 4),
            connector=False,
            color=ROLE_COLOR.get(lm.role or "", "#a0a0af"),
        )
        for lm in landmarks
    ]
    for a in conn_ids:
        n = pool[a]
        nodes.append(
            VizNode(
                id=a,
                year=n.year,
                t=_time_of(a, n.year),
                title=n.title,
                role=None,
                relevance=None,
                in_degree=0,
                score=round(n.score, 4),
                connector=True,
                color=CONNECTOR_COLOR,
            )
        )
    viz_edges = [
        VizEdge(src=e.src, dst=e.dst, intent=e.intent, thread=(e.src, e.dst) in thread_steps)
        for e in edges
        if e.src in keep and e.dst in keep
    ]
    return nodes, viz_edges


def render_png(
    nodes: list[VizNode],
    viz_edges: list[VizEdge],
    question: str,
    out_path: Path,
) -> None:
    """
    Draw the static story graph embedded in the report
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    times = [n.t for n in nodes if n.t is not None]
    if not times:
        return
    t_lo = min(times)
    pos: dict[str, tuple[float, float]] = {
        n.id: (n.t if n.t is not None else t_lo, n.score) for n in nodes
    }
    fig, ax = plt.subplots(figsize=(13, 7), facecolor="#0C0F1E")
    ax.set_facecolor("#0C0F1E")
    ax.grid(True, color="#2B3758", lw=0.4, alpha=0.6, zorder=0)
    for e in viz_edges:
        x0, y0 = pos[e.src]
        x1, y1 = pos[e.dst]
        if e.thread:
            ax.plot([x0, x1], [y0, y1], color=THREAD_COLOR, lw=1.4, alpha=0.9, zorder=2)
        else:
            ax.plot([x0, x1], [y0, y1], color=EDGE_COLOR, lw=0.5, alpha=0.55, zorder=1)
    lm_nodes = [n for n in nodes if not n.connector]
    top_label = {n.id for n in sorted(lm_nodes, key=lambda n: -n.in_degree)[:12]}
    for n in nodes:
        x, y = pos[n.id]
        size = 14 + 26 * math.sqrt(n.in_degree)
        _ = ax.scatter(
            x,
            y,
            s=size if not n.connector else 10,
            c=n.color,
            alpha=0.5 if n.connector else 0.95,
            edgecolors="none",
            zorder=3,
        )
        if n.id in top_label:
            _ = ax.annotate(
                n.id,
                (x, y),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=6,
                color="#D4D0EA",
                zorder=4,
            )
    handles = [
        Line2D([0], [0], marker="o", ls="", color=c, label=r, markersize=6)
        for r, c in ROLE_COLOR.items()
    ]
    handles.append(
        Line2D(
            [0],
            [0],
            marker="o",
            ls="",
            color=CONNECTOR_COLOR,
            label="connector",
            markersize=4,
        )
    )
    leg = ax.legend(
        handles=handles,
        loc="upper left",
        fontsize=7,
        framealpha=0.15,
        labelcolor="#D4D0EA",
    )
    leg.get_frame().set_facecolor("#171D36")
    ax.tick_params(colors="#8B95A8", labelsize=8)
    ax.ticklabel_format(axis="x", useOffset=False, style="plain")
    for spine in ax.spines.values():
        spine.set_color("#2B3758")
    _ = ax.set_xlabel("year", color="#8B95A8", fontsize=9)
    _ = ax.set_ylabel("cosine similarity", color="#8B95A8", fontsize=9)
    _ = ax.set_title(question[:110], color="#D4D0EA", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor="#0C0F1E")
    plt.close(fig)


"""
The standalone page and the dashboard tab both embed this renderer
Color variables come from the host page, and the fallbacks keep the standalone page readable
"""
GRAPH_CSS = """
.gv-wrap{display:flex;height:100%;background:var(--crust,#090B15);position:relative}
.gv-col{flex:1;display:flex;flex-direction:column;min-width:0}
.gv-bar{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap;padding:.45rem .6rem;
border-bottom:1px solid var(--surface1,#2B3758);background:var(--mantle,#171D36)}
.gv-q{border:1px solid var(--overlay0,#58637b);border-radius:9999px;
background:var(--surface0,#232E4C);color:var(--text,#D4D0EA);font:inherit;
font-size:.78rem;padding:.25rem .75rem;outline:none;width:190px}
.gv-q:focus{border-color:var(--primary,#F07898)}
.gv-role{display:inline-flex;align-items:center;gap:.3rem;
border:1px solid var(--overlay0,#58637b);border-radius:9999px;background:none;
color:var(--text,#D4D0EA);font:inherit;font-size:.72rem;padding:.15rem .55rem;
cursor:pointer}
.gv-role i{width:9px;height:9px;border-radius:50%;display:inline-block}
.gv-role.off{opacity:.35}
.gv-net{flex:1;min-width:0;min-height:0}
.gv-side{width:0;min-width:0;transition:width .25s ease;overflow:hidden;display:flex;
flex-direction:column;background:var(--mantle,#171D36);border-left:0 solid var(--overlay0,#58637b)}
.gv-wrap.open .gv-side{width:52%;min-width:360px;border-left-width:1px}
.gv-side-head{display:flex;gap:.5rem;align-items:flex-start;justify-content:space-between;
padding:.7rem .9rem .3rem}
.gv-side-head b{color:var(--primary,#F07898);font-size:.95rem;line-height:1.35}
.gv-meta-line{padding:0 .9rem;font-size:.78rem;color:var(--subtext0,#8B95A8)}
.gv-links{padding:.4rem .9rem .6rem;display:flex;gap:.5rem;flex-wrap:wrap}
.gv-btn{border:1px solid var(--overlay0,#58637b);border-radius:9999px;font-size:.78rem;
padding:.25rem .7rem;cursor:pointer;background:var(--surface0,#232E4C);
color:var(--text,#D4D0EA);text-decoration:none;font-family:inherit;display:inline-block}
.gv-btn:hover{border-color:var(--primary,#F07898)}
.gv-pdf{flex:1;display:flex}
.gv-pdf iframe{flex:1;width:100%;border:0;background:#fff}
.gv-nopdf{margin:auto;text-align:center;color:var(--subtext0,#8B95A8);font-size:.85rem;
padding:1rem;line-height:2}
.gv-chip{padding:.05rem .45rem;border-radius:9999px;font-size:.72rem;color:#090B15;
font-weight:600;white-space:nowrap;display:inline-block}
body div.vis-tooltip{background:var(--mantle,#171D36);color:var(--text,#D4D0EA);
border:1px solid var(--overlay0,#58637b);border-radius:10px;padding:.55rem .75rem;
font-family:inherit;font-size:.8rem;line-height:1.5;max-width:340px;
white-space:normal;overflow-wrap:break-word;overflow:hidden;
box-shadow:0 6px 18px rgba(0,0,0,.35)}
"""

GRAPH_JS = r"""
function renderStoryGraph(root, DATA, pdfBase, onNode){
  const css=getComputedStyle(document.documentElement);
  const V=(n,f)=>{const v=css.getPropertyValue(n).trim();return v||f;};
  const TXT=V('--text','#D4D0EA'),SUB=V('--subtext0','#8B95A8'),EDGE=V('--overlay0','#58637b');
  const GOLD='#F0C878';
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const ROLE_COLORS={foundational:'#F07898',core:'#B4A2E8',frontier:'#6FC898',
    adjacent:'#8B95A8',survey:'#5AB4D8',unrelated:'#FF5370'};
  root.innerHTML='<div class="gv-wrap"><div class="gv-col"><div class="gv-bar">'+
    '<input class="gv-q" placeholder="find a paper…">'+
    '<span class="gv-roles"></span><span style="flex:1"></span>'+
    '<button class="gv-btn gv-fit" title="zoom to fit">⌖ fit</button>'+
    '</div><div class="gv-net"></div></div><aside class="gv-side">'+
    '<div class="gv-side-head"><b></b><button class="gv-btn gv-close" title="close">✕</button></div>'+
    '<div class="gv-meta-line"></div><div class="gv-links"></div><div class="gv-pdf"></div></aside></div>';
  const wrap=root.querySelector('.gv-wrap'),side=root.querySelector('.gv-side');
  const byId={};DATA.nodes.forEach(n=>byId[n.id]=n);
  const roleOf=n=>n.connector?'connector':(n.role||'other');
  const chip=r=>r&&r!=='connector'?`<span class="gv-chip" style="background:${ROLE_COLORS[r]||'#a0a0af'}">${r}</span>`
    :'<span class="gv-chip" style="background:#58637b;color:#D4D0EA">connector</span>';
  const tip=n=>{const e=document.createElement('div');
    e.innerHTML=`<b style="color:${n.color}">${esc(n.title)}</b><br>`+
      (n.authors?`<span style="color:${SUB}">${esc(n.authors)}</span><br>`:'')+
      `<span style="font-family:ui-monospace,monospace">${n.id}</span> (${n.year??'?'}) ${chip(n.role)}<br>`+
      `<span style="color:${SUB}">in-degree ${n.in_degree} · cos ${n.score}`+
      (n.relevance!=null?` · rel ${n.relevance}`:'')+`</span><br>`+
      (n.summary?`<span style="color:${SUB}">${esc(String(n.summary).slice(0,220))}`+
        `${String(n.summary).length>220?'…':''}</span><br>`:'')+
      `<span style="color:${SUB};opacity:.75">click: read · double-click: arxiv.org</span>`;
    return e;};
  const baseOp=n=>n.connector?0.45:1.0;
  // Deterministic layout: x = publication time (month-resolved), y = cosine similarity.
  // Every node is fixed and physics is off, so the graph never wiggles.
  const T=n=>{if(n.t!=null)return n.t;
    const m=/^(?:[a-z-]+(?:\.[A-Z]{2})?\/)?(\d{2})(\d{2})/.exec(String(n.id));
    if(m){const mm=+m[2];
      if(mm>=1&&mm<=12)return(+m[1]>=90?1900:2000)+(+m[1])+(mm-1)/12;}
    return n.year!=null?n.year:(DATA.y_lo!=null?DATA.y_lo:2000);};
  const S=n=>typeof n.score==='number'?n.score:0;
  const ts=DATA.nodes.map(T),sc=DATA.nodes.map(S);
  const t0=Math.min(...ts),t1=Math.max(Math.max(...ts),t0+1);
  const s0=Math.min(...sc),s1=Math.max(Math.max(...sc),s0+0.01);
  const W=Math.max(900,Math.round((t1-t0)*170)),H=560;
  const X=t=>(t-t0)/(t1-t0)*W,Y=s=>(1-(s-s0)/(s1-s0))*H;
  const nodes=DATA.nodes.map(n=>({id:n.id,label:n.connector?undefined:n.id,
    value:Math.max(1,n.in_degree),
    color:{background:n.color,border:n.color,highlight:{background:n.color,border:TXT}},
    font:{color:TXT,size:11},x:X(T(n)),y:Y(S(n)),fixed:true,
    opacity:baseOp(n),title:tip(n)}));
  const edges=DATA.edges.map((e,i)=>({id:i,from:e.src,to:e.dst,
    arrows:{to:{enabled:true,scaleFactor:0.35}},
    color:{color:e.thread?GOLD:EDGE,opacity:e.thread?0.95:0.45},
    width:e.thread?2.2:0.7,title:e.intent||'cites'}));
  const nds=new vis.DataSet(nodes),eds=new vis.DataSet(edges);
  const net=new vis.Network(root.querySelector('.gv-net'),
    {nodes:nds,edges:eds},
    {nodes:{shape:'dot',scaling:{min:6,max:34}},physics:false,
     interaction:{hover:true,tooltipDelay:120}});
  // Axes + gridlines drawn in world coordinates beneath the nodes.
  const yearStep=(t1-t0)>40?10:(t1-t0)>18?5:(t1-t0)>8?2:1;
  net.on('beforeDrawing',ctx=>{
    ctx.save();ctx.lineWidth=1;ctx.strokeStyle=EDGE;ctx.fillStyle=SUB;
    ctx.font='11px Inter,sans-serif';
    for(let yr=Math.ceil(t0);yr<=Math.floor(t1);yr+=yearStep){
      const px=X(yr);
      ctx.globalAlpha=0.22;ctx.beginPath();ctx.moveTo(px,-30);ctx.lineTo(px,H+30);ctx.stroke();
      ctx.globalAlpha=0.9;ctx.textAlign='center';ctx.fillText(String(yr),px,H+48);
    }
    for(let i=0;i<=4;i++){
      const s=s0+i*(s1-s0)/4,py=Y(s);
      ctx.globalAlpha=0.22;ctx.beginPath();ctx.moveTo(-40,py);ctx.lineTo(W+30,py);ctx.stroke();
      ctx.globalAlpha=0.9;ctx.textAlign='right';ctx.fillText(s.toFixed(2),-50,py+4);
    }
    ctx.textAlign='center';ctx.fillText('year →',W/2,H+72);
    ctx.save();ctx.translate(-96,H/2);ctx.rotate(-Math.PI/2);
    ctx.fillText('cosine similarity →',0,0);ctx.restore();
    ctx.restore();
  });
  net.once('afterDrawing',()=>net.fit({animation:false}));
  const hidden=new Set();
  const rbox=root.querySelector('.gv-roles');
  const ROLE_ORDER=['foundational','core','frontier','adjacent','survey',
    'unrelated','other','connector'];
  [...new Set(DATA.nodes.map(roleOf))]
    .sort((a,b)=>ROLE_ORDER.indexOf(a)-ROLE_ORDER.indexOf(b)).forEach(r=>{
    const b=document.createElement('button');b.className='gv-role';b.title='toggle '+r;
    const c=r==='connector'?'#58637b':(ROLE_COLORS[r]||'#a0a0af');
    b.innerHTML=`<i style="background:${c}"></i>${r}`;
    b.onclick=()=>{b.classList.toggle('off');
      if(hidden.has(r))hidden.delete(r);else hidden.add(r);
      nds.update(DATA.nodes.filter(n=>roleOf(n)===r)
        .map(n=>({id:n.id,hidden:hidden.has(r)})));};
    rbox.appendChild(b);});
  let focused=null;
  function unfocus(){if(focused==null)return;focused=null;
    nds.update(DATA.nodes.map(n=>({id:n.id,opacity:baseOp(n)})));
    eds.update(edges.map(e=>({id:e.id,color:e.color})));}
  function focusOn(id){focused=id;
    const nb=new Set([id]);
    edges.forEach(e=>{if(e.from===id)nb.add(e.to);if(e.to===id)nb.add(e.from);});
    nds.update(DATA.nodes.map(n=>({id:n.id,opacity:nb.has(n.id)?1:0.12})));
    eds.update(edges.map(e=>({id:e.id,color:{color:e.color.color,
      opacity:(e.from===id||e.to===id)?0.95:0.05}})));}
  function show(id){const n=byId[id];if(!n)return;
    if(onNode)onNode(n);else openSide(id);}
  const qin=root.querySelector('.gv-q');
  qin.addEventListener('keydown',ev=>{
    if(ev.key!=='Enter')return;
    const q=qin.value.trim().toLowerCase();if(!q)return;
    const hit=DATA.nodes.find(n=>String(n.title||'').toLowerCase().includes(q)||
      String(n.id).includes(q));
    if(!hit)return;
    net.selectNodes([hit.id]);focusOn(hit.id);
    net.focus(hit.id,{scale:1.0,animation:true});show(hit.id);});
  root.querySelector('.gv-fit').onclick=()=>{
    unfocus();net.unselectAll();net.fit({animation:true});};
  async function openSide(id){
    const n=byId[id];if(!n)return;
    wrap.classList.add('open');
    side.querySelector('.gv-side-head b').textContent=n.title;
    side.querySelector('.gv-meta-line').innerHTML=
      `<span style="font-family:ui-monospace,monospace">${n.id}</span> (${n.year??'?'}) ${chip(n.role)}`+
      (n.relevance!=null?` rel ${n.relevance}`:'')+
      ` · in-degree ${n.in_degree} · cos ${n.score}`;
    const url=pdfBase+'/'+id;
    side.querySelector('.gv-links').innerHTML=
      `<a class="gv-btn" href="https://arxiv.org/abs/${id}" target="_blank">arxiv.org ↗</a>`+
      `<a class="gv-btn" href="${url}" target="_blank">open pdf ↗</a>`;
    const pv=side.querySelector('.gv-pdf');
    pv.innerHTML='<div class="gv-nopdf">looking for a local pdf…</div>';
    let ok=false;try{ok=(await fetch(url,{method:'HEAD'})).ok;}catch(e){}
    if(ok){pv.innerHTML=`<iframe src="${url}"></iframe>`;return;}
    pv.innerHTML='<div class="gv-nopdf">not in the local store<br>'+
      '<button class="gv-btn gv-fetch">fetch from arXiv (~10s)</button></div>';
    pv.querySelector('.gv-fetch').onclick=async ev=>{
      ev.target.textContent='fetching…';ev.target.disabled=true;
      let got=false;try{got=(await fetch(url+'?fetch=1',{method:'HEAD'})).ok;}catch(e){}
      pv.innerHTML=got?`<iframe src="${url}"></iframe>`
        :'<div class="gv-nopdf">arXiv fetch failed, use the arxiv.org link</div>';
    };
  }
  root.querySelector('.gv-close').onclick=()=>wrap.classList.remove('open');
  net.on('click',p=>{
    if(p.nodes.length){focusOn(p.nodes[0]);show(p.nodes[0]);}
    else unfocus();});
  net.on('doubleClick',p=>{
    if(p.nodes.length)window.open('https://arxiv.org/abs/'+p.nodes[0],'_blank');});
  return net;
}
"""

_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>GraphIV citation story graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body { margin:0; background:#0C0F1E; color:#D4D0EA;
         font-family:'Google Sans Flex','Noto Sans',sans-serif; }
  #bar { padding:0.6rem 1.2rem; background:#171D36; border-bottom:1px solid #58637b;
         font-size:0.85rem; display:flex; gap:1rem; align-items:center; flex-wrap:wrap; }
  #bar b { color:#F07898; }
  .lg { display:inline-flex; align-items:center; gap:0.3rem; }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
  #root { height:calc(100vh - 3rem); }
__CSS__
</style></head><body>
<div id="bar"><b>GraphIV</b><span>__QUESTION__</span>
<span style="opacity:.6">click a node &rarr; pdf sidebar &middot; double-click &rarr; arxiv.org
&middot; gold edges = lineage threads</span></div>
<div id="root"></div>
<script>
const DATA = __DATA__;
__JS__
renderStoryGraph(document.getElementById('root'), DATA, '/pdf');
</script></body></html>
"""


def render_html(
    nodes: list[VizNode],
    viz_edges: list[VizEdge],
    question: str,
    out_path: Path,
) -> None:
    """
    Write the self-contained interactive story graph
    """
    years = [n.year for n in nodes if n.year is not None]
    payload = {
        "nodes": [asdict(n) for n in nodes],
        "edges": [asdict(e) for e in viz_edges],
        "y_lo": min(years) if years else 2000,
    }
    html = (
        _HTML.replace("__QUESTION__", question[:140].replace("<", "&lt;"))
        .replace("__CSS__", GRAPH_CSS)
        .replace("__JS__", GRAPH_JS)
        .replace("__DATA__", json.dumps(payload))
    )
    _ = out_path.write_text(html, encoding="utf-8")


def render_story(
    question: str,
    landmarks: list[Landmark],
    edges: list[Edge],
    story: Story,
    pool: dict[str, PoolNode],
    out_dir: Path,
) -> dict[str, object]:
    """
    Write graph.png + graph.html into `out_dir`

    Returns counts for run.json.
    """
    nodes, viz_edges = _viz_nodes_edges(landmarks, edges, story, pool)
    try:
        render_png(nodes, viz_edges, question, out_dir / "graph.png")
    # viz must never sink a finished run
    except Exception as e:  # noqa: BLE001
        print(f"[viz] png failed: {type(e).__name__}: {e}", flush=True)
    try:
        render_html(nodes, viz_edges, question, out_dir / "graph.html")
    except Exception as e:  # noqa: BLE001
        print(f"[viz] html failed: {type(e).__name__}: {e}", flush=True)
    return {
        "nodes": len(nodes),
        "edges": len(viz_edges),
        "connectors": sum(1 for n in nodes if n.connector),
        "threads": len(story.threads),
    }
