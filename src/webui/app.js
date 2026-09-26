// The whole dashboard: a library, a run with five tabs, and one fetch each, with no build step
const PALETTES = ["haruhana", "natsumikan", "akiba", "fuyuyuki"];
const SEEDS = { haruhana: "#F07898", natsumikan: "#E08030", akiba: "#C84040", fuyuyuki: "#78B4E8" };
const TABS = ["report", "references", "graph", "details"];
const AID = /arxiv\.org\/abs\/([\w.\/-]+?)(?:v\d+)?$/;

let runs = [];
let page = 0;
let per = 15;
let filter = "";
let run = null;
let papers = [];
let byId = {};
let refFilter = "all";
let refSort = "relevance";
let refQuery = "";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// arXiv metadata carries TeX, and a title is read rather than typeset
const deTeX = (s) => String(s ?? "")
  .replace(/\$([^$]*)\$/g, "$1")
  .replace(/\\(?:text|mathrm|mathbf|emph|textit|textbf|underline)\{([^}]*)\}/g, "$1")
  .replace(/[{}\\]/g, "")
  .trim();

function authors(a) {
  const parts = deTeX(a).split(/,\s*|\s+and\s+/).filter(Boolean);
  return parts.length > 3 ? parts.slice(0, 3).join(", ") + " et al." : parts.join(", ");
}

// -- theme -----------------------------------------------------------------------------------

function apply(palette, mode) {
  document.documentElement.dataset.palette = palette;
  document.documentElement.dataset.mode = mode;
  try {
    localStorage.setItem("graphiv.palette", palette);
    localStorage.setItem("graphiv.mode", mode);
  } catch (e) { /* a private window forgets, which costs nothing */ }
  for (const b of document.querySelectorAll(".swatch")) {
    b.setAttribute("aria-pressed", String(b.dataset.palette === palette));
  }
}

function theme() {
  let palette = "haruhana";
  let mode = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  try {
    palette = localStorage.getItem("graphiv.palette") || palette;
    mode = localStorage.getItem("graphiv.mode") || mode;
  } catch (e) { /* as above */ }
  const holder = document.getElementById("swatches");
  for (const name of PALETTES) {
    const b = document.createElement("button");
    b.className = "swatch";
    b.dataset.palette = name;
    b.title = name;
    b.style.background = SEEDS[name];
    b.onclick = () => apply(name, document.documentElement.dataset.mode);
    holder.append(b);
  }
  document.getElementById("mode").onclick = () =>
    apply(document.documentElement.dataset.palette,
      document.documentElement.dataset.mode === "dark" ? "light" : "dark");
  apply(palette, mode);
}

// -- the library -----------------------------------------------------------------------------

function library() {
  const wanted = filter.trim().toLowerCase();
  const shown = runs.filter((r) => !wanted || r.question.toLowerCase().includes(wanted));
  const pages = Math.max(1, Math.ceil(shown.length / per));
  page = Math.min(page, pages - 1);
  const held = shown.slice(page * per, page * per + per);
  const cards = held.map((r) => `
    <a class="card" href="#/run/${encodeURIComponent(r.slug)}">
      <h2>${esc(r.question)}</h2>
      <div class="meta">
        <span class="chip mode">${esc(r.mode)}</span>
        <span class="chip">${r.papers} papers</span>
        <span class="chip">${esc(r.effort)}</span>
        <span>${esc(r.asked)}</span>
      </div>
    </a>`).join("");
  document.getElementById("view").innerHTML = `
    <header class="hero">
      <h1>Research Library</h1>
      <p class="sub" id="count">${runs.length} runs, every paper in them checked against the corpus</p>
      <div class="searchwrap">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
        <input type="search" id="q" placeholder="Search research topics&hellip;" value="${esc(filter)}">
      </div>
    </header>
    <div class="controls">
      <span class="pager">
        <button class="pill sm" id="prev"${page ? "" : " disabled"}>&larr;</button>
        <span>${shown.length ? page * per + 1 : 0}&ndash;${Math.min(shown.length, (page + 1) * per)} of ${shown.length}</span>
        <button class="pill sm" id="next"${page + 1 < pages ? "" : " disabled"}>&rarr;</button>
      </span>
      <select class="pill sm" id="per">
        ${[15, 30, 60, 100000].map((n) =>
          `<option value="${n}"${n === per ? " selected" : ""}>${n > 999 ? "show all" : n + " per page"}</option>`).join("")}
      </select>
    </div>
    <div class="grid">${cards || '<p class="empty">Nothing matches that.</p>'}</div>`;

  const box = document.getElementById("q");
  box.addEventListener("input", (e) => { filter = e.target.value; page = 0; library(); box.focus(); });
  box.setSelectionRange(filter.length, filter.length);
  document.getElementById("prev").onclick = () => { page--; library(); };
  document.getElementById("next").onclick = () => { page++; library(); };
  document.getElementById("per").onchange = (e) => { per = +e.target.value; page = 0; library(); };
}

// -- the panel and the hover card ------------------------------------------------------------

function closePanel() { document.getElementById("panel").classList.remove("open"); }

async function openPanel(o) {
  const panel = document.getElementById("panel");
  panel.classList.add("open");
  document.getElementById("panel-t").textContent = o.title || "";
  document.getElementById("panel-m").innerHTML = o.meta || "";
  document.getElementById("panel-l").innerHTML =
    (o.ext ? `<a class="pill sm" target="_blank" href="${o.ext}">arXiv &#8599;</a>` : "") +
    (o.url ? `<a class="pill sm" target="_blank" href="${o.url}">open in a tab &#8599;</a>` : "");
  const body = document.getElementById("panel-b");
  body.innerHTML = '<div class="panel-msg">looking for the paper&hellip;</div>';
  let there = false;
  try { there = (await fetch(o.url, { method: "HEAD" })).ok; } catch (e) { there = false; }
  if (there) { body.innerHTML = `<iframe src="${o.url}"></iframe>`; return; }
  body.innerHTML = o.abstract
    ? `<div class="panel-abs">${esc(o.abstract)}</div>`
    : '<div class="panel-msg">no pdf in the local store, and no abstract held for this paper</div>';
}

function openPaper(id) {
  hidePop();
  const p = byId[id];
  openPanel({
    title: p ? deTeX(p.title) : "arXiv:" + id,
    meta: p ? esc([authors(p.authors), p.year, p.category, id].filter(Boolean).join(" · ")) : esc(id),
    url: "pdf/" + id,
    ext: "https://arxiv.org/abs/" + id,
    abstract: p ? deTeX(p.abstract) : "",
  });
}

let pop = null;
let popTimer = null;
function hidePop() { if (pop) { pop.remove(); pop = null; } }
function hidePopSoon() { popTimer = setTimeout(hidePop, 250); }

function showPop(anchor, id) {
  clearTimeout(popTimer);
  hidePop();
  const p = byId[id];
  const buttons = `<div class="cp-b">
    <button class="pill sm" onclick="openPaper('${id}')">Read</button>
    <a class="pill sm" target="_blank" href="https://arxiv.org/abs/${id}">arXiv &#8599;</a>
    <span class="tech mono">${esc(id)}</span></div>`;
  pop = document.createElement("div");
  pop.className = "citepop";
  pop.innerHTML = p
    ? `<div class="cp-t">${esc(deTeX(p.title))}</div>
       <div class="cp-m">${esc(authors(p.authors))}${p.authors ? " · " : ""}${p.year || ""}
       ${p.role ? `<span class="rolechip role-${p.role}">${p.role}</span>` : ""}
       ${p.magnet != null ? `<span class="tech">argued with ${p.magnet}</span>` : ""}</div>
       ${p.abstract ? `<div class="cp-s">${esc(deTeX(p.abstract))}</div>` : ""}${buttons}`
    : `<div class="cp-m mono">arXiv:${esc(id)}</div>${buttons}`;
  const box = anchor.getBoundingClientRect();
  pop.style.left = Math.min(box.left + scrollX, scrollX + innerWidth - 420) + "px";
  pop.style.top = box.bottom + scrollY + 6 + "px";
  pop.addEventListener("mouseenter", () => clearTimeout(popTimer));
  pop.addEventListener("mouseleave", hidePopSoon);
  document.body.append(pop);
}

function hookCitations(el) {
  for (const a of el.querySelectorAll('a[href*="arxiv.org/abs/"]')) {
    const found = (a.getAttribute("href") || "").match(AID);
    if (!found) continue;
    const id = found[1];
    a.addEventListener("click", (e) => {
      if (e.ctrlKey || e.metaKey) return;
      e.preventDefault();
      openPaper(id);
    });
    a.addEventListener("mouseenter", () => showPop(a, id));
    a.addEventListener("mouseleave", hidePopSoon);
  }
}

// -- the report ------------------------------------------------------------------------------

function decorate(article) {
  for (const table of article.querySelectorAll("table")) {
    const wrap = document.createElement("div");
    wrap.className = "tablewrap";
    table.replaceWith(wrap);
    wrap.append(table);
  }
  for (const code of article.querySelectorAll("li > code:first-child")) {
    const role = code.textContent.trim();
    code.className = `rolechip role-${role}`;
    code.textContent = role;
  }
  hookCitations(article);
}

function contents(article) {
  const nav = document.createElement("nav");
  nav.className = "toc";
  for (const head of article.querySelectorAll("h2, h3")) {
    const link = document.createElement("a");
    link.href = "#";
    link.textContent = head.textContent;
    if (head.tagName === "H3") link.className = "sub";
    link.onclick = (e) => { e.preventDefault(); head.scrollIntoView({ block: "start" }); };
    nav.append(link);
  }
  return nav;
}

const SECTIONS = [
  ["about", "What this is about"],
  ["facts", "What we know"],
  ["methods", "The methods"],
  ["active", "Active research"],
  ["open", "Unanswered questions"],
  ["disagree", "Where the field disagrees"],
];

// one strip of buttons over one panel, which is how a section holds several things at one depth
function subtabs(host, items, draw) {
  if (!items.length) return;
  const strip = document.createElement("div");
  strip.className = "subtabs";
  const panel = document.createElement("div");
  panel.className = "subpanel";
  const show = (i) => {
    for (const [j, b] of [...strip.children].entries()) b.classList.toggle("on", i === j);
    panel.replaceChildren(draw(items[i], i));
  };
  items.forEach((item, i) => {
    const b = document.createElement("button");
    b.className = "subtab";
    b.innerHTML = item.label;
    b.onclick = () => show(i);
    strip.append(b);
  });
  host.append(strip, panel);
  show(0);
}

function prose(markdown) {
  const el = document.createElement("div");
  el.className = "prose";
  el.innerHTML = marked.parse(markdown || "");
  decorate(el);
  return el;
}

function paperLine(p, extra) {
  const role = p.role || "ungraded";
  return `<li>
    <span class="rolechip role-${role}">${role}</span>
    <span class="pl-date">${esc(p.date || "")}</span>
    <a href="#" onclick="openPaper('${p.arxiv_id}');return false">${esc(deTeX(p.title || p.arxiv_id))}</a>
    ${extra || ""}</li>`;
}

function reportTab(run) {
  const panel = document.getElementById("p-report");
  const got = run.sections || {};
  const column = document.createElement("div");
  column.className = "sections";

  const block = (key, title, lead) => {
    const el = document.createElement("section");
    el.id = "s-" + key;
    el.className = "rsection";
    el.innerHTML = `<h2>${title}</h2>${lead ? `<p class="lead">${lead}</p>` : ""}`;
    column.append(el);
    return el;
  };

  // 1, what this is about
  const about = block("about", "What this is about");
  about.append(prose(got.opening || "This run wrote no opening, which the quick preset does not."));

  // 2, what we know, one tab per claim the review makes
  const facts = block("facts", "What we know",
    "Each of these is a claim about the field, argued from the papers that carry it.");
  const claims = (got.claims || []).map((c, i) => ({ label: `${i + 1}. ${esc(c.title)}`, ...c }));
  if (claims.length) subtabs(facts, claims, (c) => prose(`### ${c.title}\n\n${c.body}`));
  else facts.append(prose("Nothing was written for this run."));

  // 3, the methods
  const methods = block("methods", "The methods",
    "One row per method rather than per paper, on the axes this question turns on.");
  const m = got.methods || {};
  if (m.table) {
    const views = [
      { label: "side by side", md: m.table },
      ...(m.spread ? [{ label: "what people are doing", md: m.spread }] : []),
      ...(m.gaps ? [{ label: "what nobody has tried", md: m.gaps }] : []),
    ];
    subtabs(methods, views, (v) => prose(v.md));
  } else methods.append(prose("No method table in this run, which the quick preset does not build."));

  // 4, active research, one tab per area and one for what has just appeared
  const active = block("active", "Active research",
    "What each area is doing now, and what has appeared against it since.");
  const areas = (got.areas || []).map((a, i) => ({ label: `area ${i + 1}`, ...a }));
  const tabs = [...areas];
  if ((got.successors || []).length) tabs.push({ label: "just appeared", fresh: true });
  subtabs(active, tabs, (t) => {
    const el = document.createElement("div");
    if (t.fresh) {
      el.innerHTML = `<p class="lead">Each of these cites a paper above and takes a position on it,
        so none of them needs a citation of its own to be found.</p>
        <ul class="papers">${got.successors.map((s) => paperLine(
          { ...s, role: "frontier" },
          `<span class="tech">${esc(s.intents.join(", "))}, against ${s.reach}</span>
           ${s.sentence ? `<blockquote>${esc(s.sentence)}</blockquote>` : ""}`)).join("")}</ul>`;
      return el;
    }
    const held = t.papers.map((id) => byId[id]).filter(Boolean);
    el.innerHTML = `<p class="lead">${esc(t.question)}</p>
      <ul class="papers">${by_role_list(held)}</ul>`;
    return el;
  });

  // 5, unanswered, one tab per area
  const open = block("open", "Unanswered questions",
    "Read out of the limitations and future work sections of the papers themselves.");
  const withOpen = areas.filter((a) => (a.unanswered || []).length);
  if (withOpen.length) {
    subtabs(open, withOpen, (a) => {
      const el = document.createElement("div");
      el.innerHTML = `<p class="lead">${esc(a.question)}</p>
        <ul class="opens">${a.unanswered.map((q) => `<li>${linkIds(esc(q))}</li>`).join("")}</ul>`;
      hookCitations(el);
      return el;
    });
  } else open.append(prose("No paper in this run carried a limitations section on disk."));

  // 6, where the field disagrees
  const dis = block("disagree", "Where the field disagrees",
    "One paper telling another it is wrong, in the words it used.");
  const rows = got.disputes || [];
  dis.innerHTML += rows.length
    ? `<ul class="disputes">${rows.map((d) => `<li>
        <div class="d-head">on <a href="#" onclick="openPaper('${d.arxiv_id}');return false">${esc(deTeX((byId[d.arxiv_id] || {}).title || d.arxiv_id))}</a>
        <span class="chip">${esc(d.intent)}</span>
        <span class="tech">said by <a href="#" onclick="openPaper('${d.by}');return false">${esc(d.by)}</a></span></div>
        <blockquote>${esc(d.sentence)}</blockquote></li>`).join("")}</ul>`
    : '<p class="lead">No labeled disagreement inside this run.</p>';

  const nav = document.createElement("nav");
  nav.className = "toc";
  nav.innerHTML = SECTIONS.map(([k, t], i) =>
    `<a href="#" data-s="s-${k}"><span class="tocn">${i + 1}</span>${t}</a>`).join("");
  for (const a of nav.children) {
    a.onclick = (e) => {
      e.preventDefault();
      document.getElementById(a.dataset.s).scrollIntoView({ block: "start" });
    };
  }
  const grid = document.createElement("div");
  grid.className = "readwrap";
  grid.append(nav, column);
  panel.replaceChildren(grid);
  spy(nav, column);
}

// the id in an open question is written bare, so it is linked here rather than by the writer
function linkIds(text) {
  return text.replace(/\[((?:[a-z][a-z.\-]+\/\d{7}|\d{4}\.\d{4,5}))\]/gi,
    (_, id) => `<a href="https://arxiv.org/abs/${id}">${id}</a>`);
}

function by_role_list(papers) {
  const order = ["foundational", "core", "frontier", "survey", "adjacent", "unrelated", ""];
  return [...papers]
    .sort((a, b) => order.indexOf(a.role || "") - order.indexOf(b.role || ""))
    .map((p) => paperLine(p, p.cited ? '<span class="cited-b">CITED</span>' : ""))
    .join("");
}

function spy(nav, column) {
  const seen = new Map();
  const mark = () => {
    let best = null;
    for (const [el, ratio] of seen) if (ratio > 0 && (!best || el.offsetTop < best.offsetTop)) best = el;
    for (const a of nav.children) a.classList.toggle("here", best && a.dataset.s === best.id);
  };
  const watch = new IntersectionObserver((rows) => {
    for (const r of rows) seen.set(r.target, r.intersectionRatio);
    mark();
  }, { rootMargin: "-70px 0px -60% 0px", threshold: [0, 0.01] });
  for (const s of column.children) watch.observe(s);
}

// -- references ------------------------------------------------------------------------------

function refItem(p) {
  const meta = [authors(p.authors), p.year, p.category].filter(Boolean).join(" · ");
  const numbers = [
    p.relevance != null ? `relevance ${p.relevance}` : "",
    p.cosine != null ? `cosine ${p.cosine}` : "",
    p.magnet != null ? `argued with ${p.magnet}` : "",
  ].filter(Boolean).join(" · ");
  return `<div class="ref">
    <div class="ref-main">
      <div class="ref-t"><a href="#" onclick="openPaper('${p.arxiv_id}');return false">${esc(deTeX(p.title))}</a>${p.cited ? '<span class="cited-b">CITED</span>' : ""}</div>
      <div class="ref-m">${esc(meta)}${p.role ? `<span class="rolechip role-${p.role}">${p.role}</span>` : ""}${p.retrieved ? "" : '<span class="chip">from the graph</span>'}</div>
      <div class="tech mono">${esc(p.arxiv_id)}${numbers ? " · " + numbers : ""}</div>
      ${p.abstract ? `<p class="ref-s">${esc(deTeX(p.abstract))}</p>` : ""}
    </div>
    <div class="ref-side">
      <button class="pill sm" onclick="openPaper('${p.arxiv_id}')">Read</button>
      <a class="pill sm" target="_blank" href="https://arxiv.org/abs/${p.arxiv_id}">arXiv &#8599;</a>
    </div></div>`;
}

function referencesTab() {
  const host = document.getElementById("p-references");
  if (!papers.length) { host.innerHTML = '<p class="empty">no papers recorded for this run</p>'; return; }
  let shown = papers.filter((p) =>
    refFilter === "all" ||
    (refFilter === "cited" && p.cited) ||
    (refFilter === "uncited" && !p.cited) ||
    (refFilter === "graph" && !p.retrieved));
  if (refQuery) {
    shown = shown.filter((p) => `${p.title} ${p.authors} ${p.abstract} ${p.arxiv_id}`
      .toLowerCase().includes(refQuery));
  }
  const key = refSort;
  shown = [...shown].sort((a, b) =>
    key === "relevance" ? (b.relevance ?? -9) - (a.relevance ?? -9) || (b.cosine ?? 0) - (a.cosine ?? 0)
    : key === "year" ? String(b.date).localeCompare(String(a.date))
    : (b[key] ?? -1e9) - (a[key] ?? -1e9));
  host.innerHTML = `
    <div class="rtools">
      <input type="search" id="rq" placeholder="filter these papers&hellip;" value="${esc(refQuery)}">
      <select class="pill sm" id="rfilter">
        ${[["all", "every paper"], ["cited", "cited in the report"], ["uncited", "not cited"], ["graph", "found by the graph"]]
          .map(([v, l]) => `<option value="${v}"${v === refFilter ? " selected" : ""}>${l}</option>`).join("")}
      </select>
      <select class="pill sm" id="rsort">
        ${[["relevance", "by relevance"], ["year", "by date"], ["cosine", "by closeness"], ["magnet", "by how argued with"]]
          .map(([v, l]) => `<option value="${v}"${v === refSort ? " selected" : ""}>${l}</option>`).join("")}
      </select>
      <span class="byline">${shown.length} of ${papers.length} · ${papers.filter((p) => p.cited).length} cited</span>
    </div>
    <div class="reflist">${shown.map(refItem).join("") || '<p class="empty">nothing matches</p>'}</div>`;
  const box = document.getElementById("rq");
  box.addEventListener("input", (e) => { refQuery = e.target.value.toLowerCase(); referencesTab(); document.getElementById("rq").focus(); });
  document.getElementById("rfilter").onchange = (e) => { refFilter = e.target.value; referencesTab(); };
  document.getElementById("rsort").onchange = (e) => { refSort = e.target.value; referencesTab(); };
}

// -- the graph -------------------------------------------------------------------------------

const ROLES = ["foundational", "core", "frontier", "adjacent", "survey", "unrelated", "connector", "ungraded"];
let hiddenRoles = new Set();
let focusedLine = 0;
let focusedNode = null;

function graphTab(graph) {
  const host = document.getElementById("p-graph");
  if (!graph || !graph.nodes || !graph.nodes.length) {
    host.innerHTML = '<p class="empty">no graph for this run</p>';
    return;
  }
  const roles = ROLES.filter((r) => graph.nodes.some((n) => n.role === r));
  const lines = [...new Set(graph.nodes.flatMap((n) => n.lines))].sort((a, b) => a - b);
  host.innerHTML = `
    <div class="gtools">
      <span class="glegend">${roles.map((r) =>
        `<button class="grole${hiddenRoles.has(r) ? " off" : ""}" data-r="${r}"><i class="role-dot role-${r}"></i>${r}</button>`).join("")}</span>
      <span class="gspacer"></span>
      <select class="pill sm" id="gline">
        <option value="0">every path</option>
        ${lines.map((l) => `<option value="${l}"${l === focusedLine ? " selected" : ""}>line ${l} only</option>`).join("")}
      </select>
      <input type="search" id="gq" placeholder="find a paper&hellip;">
    </div>
    <div class="gwrap" id="gwrap"></div>
    <p class="byline" style="margin:10px 0 14px">Time runs left to right and closeness to the question runs up.
      A bigger dot is cited more often. A gold line is a path the walk reproduced. Click a dot to read the paper.</p>
    <div id="paths"></div>`;
  for (const b of host.querySelectorAll(".grole")) {
    b.onclick = () => {
      const r = b.dataset.r;
      if (hiddenRoles.has(r)) hiddenRoles.delete(r); else hiddenRoles.add(r);
      graphTab(graph);
    };
  }
  document.getElementById("gline").onchange = (e) => { focusedLine = +e.target.value; graphTab(graph); };
  const box = document.getElementById("gq");
  box.oninput = (e) => {
    const q = e.target.value.trim().toLowerCase();
    focusedNode = q ? (graph.nodes.find((n) => n.title.toLowerCase().includes(q) || n.arxiv_id.includes(q)) || {}).arxiv_id : null;
    drawGraph(graph);
    document.getElementById("gq").focus();
  };
  drawGraph(graph);
  pathList();
}

// a path is a claim about how the field moved, so it is readable rather than only drawn
function pathList() {
  const host = document.getElementById("paths");
  if (!host) return;
  const lines = (run.sections || {}).lineages || [];
  if (!lines.length) { host.innerHTML = ""; return; }
  const shown = focusedLine ? [lines[focusedLine - 1]].filter(Boolean) : lines;
  host.innerHTML = `<h3 class="pathh">${focusedLine ? "Line " + focusedLine : "Every path the walk reproduced"}</h3>` +
    shown.map((line, i) => {
      const n = focusedLine || i + 1;
      return `<div class="path">
        <button class="pathtop" onclick="focusedLine=${focusedLine ? 0 : n};graphTab(run.graph);">
          <b>line ${n}</b>
          <span class="tech">${line.papers.length} papers, ${line.papers[0].date.slice(0, 4)} to ${line.papers[line.papers.length - 1].date.slice(0, 4)}, reproduced ${line.runs === 1 ? "once" : line.runs + " times"}</span>
          <span class="tech">${focusedLine ? "show every path" : "isolate"}</span>
        </button>
        <ol class="pathsteps">${line.papers.map((p) => `<li${p.magnet ? ' class="magnet"' : ""}>
          <span class="pl-date">${p.date}</span>
          <a href="#" onclick="openPaper('${p.arxiv_id}');return false">${esc(deTeX(p.title))}</a>
          ${p.magnet ? '<span class="chip">argued with</span>' : ""}</li>`).join("")}</ol>
      </div>`;
    }).join("");
}

function drawGraph(graph) {
  const host = document.getElementById("gwrap");
  const shown = graph.nodes.filter((n) => !hiddenRoles.has(n.role) &&
    (!focusedLine || n.lines.includes(focusedLine)));
  if (!shown.length) { host.innerHTML = '<p class="empty">every role is hidden</p>'; return; }
  const held = new Set(shown.map((n) => n.arxiv_id));
  const at = shown.map((n) => Date.parse(n.date));
  const cos = shown.map((n) => n.cosine ?? 0);
  const t0 = Math.min(...at);
  const t1 = Math.max(Math.max(...at), t0 + 8.64e7);
  const c0 = Math.min(...cos);
  const c1 = Math.max(Math.max(...cos), c0 + 0.01);
  const years = (t1 - t0) / 3.156e10;
  const pad = { l: 66, r: 30, t: 22, b: 52 };
  // the whole span has to be visible without scrolling, since the paths are read left to right
  const room = (document.getElementById("gwrap") || {}).clientWidth || 1100;
  const width = Math.max(900, Math.min(room - 2, Math.round(years * 150) + pad.l + pad.r));
  const height = 620;
  const X = (d) => pad.l + ((Date.parse(d) - t0) / (t1 - t0)) * (width - pad.l - pad.r);
  const Y = (c) => pad.t + (1 - ((c ?? 0) - c0) / (c1 - c0)) * (height - pad.t - pad.b);
  const R = (n) => 3.5 + 7 * Math.sqrt(Math.min(1, (n.cited_by || 0) / 400));

  const grid = [];
  const step = years > 24 ? 5 : years > 10 ? 2 : 1;
  for (let y = new Date(t0).getFullYear(); y <= new Date(t1).getFullYear(); y += step) {
    const x = X(`${y}-01-01`);
    if (x < pad.l - 1 || x > width - pad.r) continue;
    grid.push(`<line class="grid" x1="${x}" y1="${pad.t}" x2="${x}" y2="${height - pad.b}"/>
      <text class="gaxis" x="${x}" y="${height - pad.b + 18}" text-anchor="middle">${y}</text>`);
  }
  for (let i = 0; i <= 4; i++) {
    const c = c0 + (i * (c1 - c0)) / 4;
    const y = Y(c);
    grid.push(`<line class="grid" x1="${pad.l}" y1="${y}" x2="${width - pad.r}" y2="${y}"/>
      <text class="gaxis" x="${pad.l - 10}" y="${y + 4}" text-anchor="end">${c.toFixed(2)}</text>`);
  }
  grid.push(`<text class="gaxis" x="${width / 2}" y="${height - 12}" text-anchor="middle">year &rarr;</text>`);
  grid.push(`<text class="gaxis" transform="translate(16 ${height / 2}) rotate(-90)" text-anchor="middle">closeness to the question &rarr;</text>`);

  const neighbours = new Set();
  if (focusedNode) {
    neighbours.add(focusedNode);
    for (const e of graph.edges) {
      if (e.source === focusedNode) neighbours.add(e.target);
      if (e.target === focusedNode) neighbours.add(e.source);
    }
  }
  const dim = (id) => (focusedNode && !neighbours.has(id) ? 0.08 : 1);
  const byId2 = Object.fromEntries(shown.map((n) => [n.arxiv_id, n]));
  const edges = graph.edges
    .filter((e) => held.has(e.source) && held.has(e.target))
    .map((e) => {
      const a = byId2[e.source];
      const b = byId2[e.target];
      const on = e.walked;
      const alpha = Math.min(dim(e.source), dim(e.target)) * (on ? 0.95 : 0.3);
      return `<line class="${on ? "gwalk" : "gedge"}" x1="${X(a.date)}" y1="${Y(a.cosine)}" x2="${X(b.date)}" y2="${Y(b.cosine)}" opacity="${alpha}"/>`;
    }).join("");

  const dots = shown.map((n) => {
    const on = n.lines.length > 0;
    return `<g class="gnode" opacity="${dim(n.arxiv_id)}" onclick="openPaper('${n.arxiv_id}')">
      <title>${esc(deTeX(n.title))}
${n.arxiv_id} (${n.date}) ${n.role}
cited by ${n.cited_by}, closeness ${n.cosine ?? "?"}${n.lines.length ? ", line " + n.lines.join(" and ") : ""}</title>
      <circle class="role-fill role-${n.role}" cx="${X(n.date)}" cy="${Y(n.cosine)}" r="${R(n)}"
        stroke="${on ? "var(--yellow)" : "var(--mantle)"}" stroke-width="${on ? 2 : 1}"/>
    </g>`;
  }).join("");

  const placed = [];
  const labels = shown
    .filter((n) => n.lines.length || n.magnet > 0.4)
    .sort((a, b) => b.magnet - a.magnet)
    .map((n) => {
      const x = X(n.date) + R(n) + 6;
      const y = Y(n.cosine) + 4;
      if (placed.some((p) => Math.abs(p.y - y) < 13 && Math.abs(p.x - x) < 230)) return "";
      placed.push({ x, y });
      return `<text class="glabel" x="${x}" y="${y}">${esc(deTeX(n.title).slice(0, 30))}</text>`;
    })
    .filter(Boolean)
    .slice(0, 18)
    .join("");

  host.innerHTML = `<svg width="${width}" height="${height}" role="img">
    ${grid.join("")}${edges}${dots}${labels}</svg>`;
}

// -- methods and details ---------------------------------------------------------------------

function detailsTab() {
  const counts = run.counts || {};
  const seconds = run.seconds || {};
  const rows = (o, unit) => Object.entries(o)
    .map(([k, v]) => `<div class="drow"><span>${esc(k)}</span><span>${typeof v === "number" ? v.toLocaleString() : esc(v)}${unit || ""}</span></div>`)
    .join("") || '<div class="drow"><span>nothing recorded</span><span></span></div>';
  const areas = (run.areas || []).map((a) =>
    `<div class="drow"><span>${esc(a.question)}</span><span>${a.papers.length}</span></div>`).join("");
  const guard = [
    `<div class="drow"><span>ids corrected</span><span>${Object.keys(run.corrected || {}).length}</span></div>`,
    `<div class="drow"><span>ids cut as invented</span><span>${(run.cut || []).length}</span></div>`,
    `<div class="drow"><span>ids cited and verified</span><span>${(run.cited || []).length}</span></div>`,
  ].join("");
  document.getElementById("p-details").innerHTML = `<div class="dgrid">
    <div class="dcard"><h3>What the run did</h3>${rows(counts)}</div>
    <div class="dcard"><h3>What it cost</h3>${rows(seconds, "s")}</div>
    <div class="dcard"><h3>The grounding guard</h3>${guard}</div>
    <div class="dcard"><h3>The areas it searched</h3>${areas || '<div class="drow"><span>one question, unsplit</span><span></span></div>'}</div>
    <div class="dcard"><h3>The run</h3>
      <div class="drow"><span>asked as of</span><span>${esc(run.asked)}</span></div>
      <div class="drow"><span>mode</span><span>${esc(run.mode)}</span></div>
      <div class="drow"><span>effort</span><span>${esc(run.effort)}</span></div>
      <div class="drow"><span>retrievals</span><span>${(run.queries || []).length}</span></div>
    </div></div>`;
}

// -- one run ---------------------------------------------------------------------------------

function tab(name, quiet) {
  if (!TABS.includes(name)) name = "report";
  if (!quiet && run) location.hash = `#/run/${encodeURIComponent(run.slug)}/${name}`;
  for (const p of document.querySelectorAll(".tab-panel")) p.classList.toggle("active", p.id === "p-" + name);
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("active", b.dataset.t === name);
}

async function reading(slug, wanted) {
  const view = document.getElementById("view");
  view.innerHTML = '<p class="empty">loading&hellip;</p>';
  const answer = await fetch(`api/runs/${encodeURIComponent(slug)}`);
  if (!answer.ok) { view.innerHTML = `<p class="empty">No run called ${esc(slug)}.</p>`; return; }
  run = await answer.json();
  // papers.json overwrites run.json's id list, and an older run that has only ids gets none
  papers = (run.papers || []).filter((p) => typeof p === "object");
  byId = Object.fromEntries(papers.map((p) => [p.arxiv_id, p]));
  document.title = "GraphIV, " + run.question;

  const files = ["report.md", "run.json", "papers.json", "graph.json"]
    .map((f) => `<a class="mi mono" href="files/${encodeURIComponent(slug)}/${f}" target="_blank">${f}</a>`).join("");
  const byline = [run.asked, `${papers.length || (run.papers || []).length} papers`,
    `${(run.cited || []).length} cited`, run.mode, run.effort].filter(Boolean).join(" · ");
  view.innerHTML = `
    <div class="runhead">
      <a class="back" href="#/">&larr; Library</a>
      <h1 class="q">${esc(run.question)}</h1>
      <div class="byline">${esc(byline)}</div>
      <div class="tech mono">${esc(slug)}</div>
      <div class="actionbar">
        <button class="ab-btn primary" id="topcited">Read the first paper</button>
        <details class="menu"><summary class="ab-btn">Download &#9662;</summary>
          <div class="menu-body">${files}</div></details>
      </div>
    </div>
    <div class="tabs">${[["report", "Report"], ["references", "References"], ["graph", "Graph"], ["details", "Details"]]
      .map(([t, l]) => `<button data-t="${t}" onclick="tab('${t}')">${l}</button>`).join("")}</div>
    <div class="tab-panel" id="p-report"></div>
    <div class="tab-panel" id="p-references"></div>
    <div class="tab-panel" id="p-graph"></div>
    <div class="tab-panel" id="p-details"></div>`;

  reportTab(run);
  referencesTab();
  graphTab(run.graph);
  detailsTab();
  const first = papers.find((p) => p.cited) || papers[0];
  document.getElementById("topcited").onclick = () => first && openPaper(first.arxiv_id);
  tab(wanted || "report", true);
  window.scrollTo(0, 0);
}

// -- routing ---------------------------------------------------------------------------------

function route() {
  closePanel();
  const where = location.hash.replace(/^#/, "");
  if (where.startsWith("/run/")) {
    const parts = where.slice(5).split("/");
    const slug = decodeURIComponent(parts[0]);
    if (run && run.slug === slug) return tab(parts[1] || "report", true);
    return reading(slug, parts[1]);
  }
  run = null;
  library();
}

async function start() {
  theme();
  window.addEventListener("hashchange", route);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePanel(); });
  try { runs = await (await fetch("api/runs")).json(); } catch (e) { runs = []; }
  route();
}

start();
