"""
Every browser-side script the dashboard ships, as string constants

They are inlined rather than served as files because the page has no build step.
"""

from __future__ import annotations

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
"""
)


_ADMIN_JS = r"""
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
async function delRun(s,c){
  if(await act('delete',s,c)){RUNS=RUNS.filter(r=>!(r.slug===s&&r.config===c));render();}
}
async function actRun(name){
  const ok=await act(name,SLUG,CFG);
  if(ok&&name==='delete')location.href='/';
}
window.GIV_ADMIN={
 cardDelete:r=>`<button class="mi danger" onclick="delRun('${r.slug}','${r.config}')">delete…</button>`,
};
"""


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
          ${window.GIV_ADMIN?GIV_ADMIN.cardDelete(r):''}
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
function mathify(el){
  if(!window.renderMathInElement)return;
  renderMathInElement(el,{delimiters:[
    {left:'$$',right:'$$',display:true},
    {left:'\\[',right:'\\]',display:true},
    {left:'\\(',right:'\\)',display:false},
    {left:'$',right:'$',display:false}],
   ignoredTags:['script','noscript','style','textarea','pre','code'],
   throwOnError:false});
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
    if(window.Prism)Prism.highlightAllUnder(rel);mathify(rel);}
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
