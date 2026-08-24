"""
The browser half: fetch an item, paint it, and take the keystroke that labels it

State lives in the server, so a reload resumes exactly where the session was
"""

from __future__ import annotations

_APP_JS: str = """
let item = null, picked = {}, t0 = 0, page = 0;
const INTENT_KEYS = '123456';
let AXES = [];

function esc(s){const d=document.createElement('div');d.textContent=s==null?'':String(s);
return d.innerHTML;}

async function load(){
  const s = await (await fetch('/api/state')).json();
  AXES = s.axes;
  document.getElementById('n-done').textContent = s.done;
  document.getElementById('n-total').textContent = s.total;
  document.getElementById('barfill').style.width = (100*s.done/s.total) + '%';
  if(!s.item){ document.getElementById('split').style.display='none';
    document.getElementById('fin').style.display='block'; return; }
  item = s.item; picked = {}; page = item.page; t0 = Date.now();
  paint(); showPage(page);
}

function paint(){
  document.getElementById('sentence').innerHTML = mark(item.sentence, item.needles);
  document.getElementById('section').textContent = item.section;
  document.getElementById('ordinal').textContent = item.ordinal;
  fill('citing', item.citing);
  fill('cited', item.cited);
  document.getElementById('citing-abs').textContent = item.abstract || '';
  const hint = {intent:item.hint_intent};
  document.getElementById('axes').innerHTML = AXES.map(ax =>
    '<div class="axis"><h4>' + esc(ax.name) + '</h4><div class="opts">' +
    ax.options.map((o,i) =>
      '<div class="opt' + (hint[ax.name] === o ? ' hint' : '') +
      '" data-axis="' + esc(ax.name) + '" data-opt="' + esc(o) + '">' +
      '<kbd>' + esc(ax.keys[i]) + '</kbd>' + esc(o) + '</div>').join('') +
    '</div></div>').join('');
  document.getElementById('guess').innerHTML = item.hint_intent
    ? 'student-v3 says <b>' + esc(item.hint_intent) + '</b>'
    : 'student-v3 has no label for this one';
  document.querySelectorAll('.opt').forEach(el => el.onclick = () =>
    pick(el.dataset.axis, el.dataset.opt));
}

function fill(which, p){
  document.getElementById(which + '-title').textContent = p.title || '(no title)';
  document.getElementById(which + '-authors').textContent = p.authors || '';
  const id = document.getElementById(which + '-id');
  id.textContent = p.arxiv_id ? ('arXiv:' + p.arxiv_id) : '(unresolved)';
  id.href = p.arxiv_id ? ('https://arxiv.org/abs/' + p.arxiv_id) : '#';
  document.getElementById(which + '-facts').textContent =
    [p.year, p.category].filter(Boolean).join('  ·  ');
}

function mark(text, needles){
  let out = esc(text);
  (needles || []).forEach(n => {
    const safe = esc(n).replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
    out = out.replace(new RegExp(safe, 'i'), m => '<mark>' + m + '</mark>');
  });
  return out;
}

function showPage(p){
  if(!item.pages){ return; }
  page = Math.max(0, Math.min(item.pages - 1, p));
  document.getElementById('page').src =
    '/api/page?citing_id=' + item.citing_id + '&ordinal=' + item.ordinal + '&page=' + page;
  document.getElementById('pageno').textContent = (page + 1) + ' / ' + item.pages;
}

function pick(axis, opt){
  picked[axis] = opt;
  document.querySelectorAll('.opt').forEach(el =>
    el.classList.toggle('sel', picked[el.dataset.axis] === el.dataset.opt));
  if(AXES.every(ax => picked[ax.name])) commit();
}

async function commit(){
  const body = {citing_id:item.citing_id, ordinal:item.ordinal, labels:picked,
                ms:Date.now()-t0};
  await fetch('/api/label', {method:'POST', body:JSON.stringify(body)});
  load();
}

async function skip(){
  await fetch('/api/label', {method:'POST', body:JSON.stringify(
    {citing_id:item.citing_id, ordinal:item.ordinal, labels:{_skipped:'1'},
     ms:Date.now()-t0})});
  load();
}

async function undo(){ await fetch('/api/undo', {method:'POST'}); load(); }

document.addEventListener('keydown', e => {
  if(!item) return;
  const k = e.key.toLowerCase();
  const i = INTENT_KEYS.indexOf(k);
  if(i >= 0 && AXES[0]) return pick(AXES[0].name, AXES[0].options[i]);
  if(k === 't') return toggleHint();
  if(k === 'u') return undo();
  if(k === 'x') return skip();
  if(k === 'arrowleft' || k === '[') return showPage(page - 1);
  if(k === 'arrowright' || k === ']') return showPage(page + 1);
  if(k === 'h') return showPage(item.page);
});

function toggleHint(){
  const off = document.documentElement.getAttribute('data-hint') === 'off';
  document.documentElement.setAttribute('data-hint', off ? 'on' : 'off');
  localStorage.setItem('label-hint', off ? 'on' : 'off');
}
document.getElementById('hint-btn').onclick = toggleHint;
document.documentElement.setAttribute('data-hint',
  localStorage.getItem('label-hint') || 'on');

document.getElementById('mode').onclick = () => {
  const now = document.documentElement.getAttribute('data-mode') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-mode', now);
  localStorage.setItem('label-mode', now);
};
document.documentElement.setAttribute('data-mode',
  localStorage.getItem('label-mode') || 'light');

load();
"""
