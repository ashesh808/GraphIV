// The whole dashboard: a library, a run with five tabs, and one fetch each, with no build step
const PALETTES = ["haruhana", "natsumikan", "akiba", "fuyuyuki"];
const SEEDS = { haruhana: "#F07898", natsumikan: "#E08030", akiba: "#C84040", fuyuyuki: "#78B4E8" };
const TABS = ["report", "methods", "references", "graph", "topics", "details"];
const AID = /arxiv\.org\/abs\/([\w.\/-]+?)(?:v\d+)?$/;
const ROLE_ORDER = ["foundational", "core", "frontier", "survey", "adjacent", "unrelated", "connector", "ungraded"];
const LINE_COLORS = ["--yellow", "--sky", "--green", "--secondary", "--primary", "--red", "--tertiary"];

// a citation edge reads as a sentence, the citing paper first
const INTENTS = {
  extends: "builds on",
  uses: "uses",
  compares: "compares itself against",
  critiques: "critiques",
  motivates: "was motivated by",
  background: "mentions",
};

let runs = [];
let page = 0;
let per = 15;
let filter = "";
let run = null;
let papers = [];
let byId = {};
let nodeById = {};
let lineNames = [];

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

const capital = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const titleOf = (id) => deTeX((byId[id] || nodeById[id] || {}).title || id);
const yearOf = (id) => String((byId[id] || nodeById[id] || {}).date || "").slice(0, 4);
const lineName = (n) => lineNames[n - 1] || `Line ${n}`;
const lineColor = (n) => `var(${LINE_COLORS[(n - 1) % LINE_COLORS.length]})`;

function longDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return isNaN(d) ? iso || "" : d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

function duration(seconds) {
  const s = Math.round(seconds);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

// the writer cites as arXiv:<id> in plain text, which is linked here so the hover card finds it
function linkPlain(markdown) {
  return String(markdown || "").replace(/(?<![\[\/])arXiv:(\d{4}\.\d{4,5}|[a-z][a-z.\-]+\/\d{7})(?![\]\w])/g,
    (_, id) => `[arXiv:${id}](https://arxiv.org/abs/${id})`);
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
        <span class="chip mode">${esc(capital(r.mode))}</span>
        <span class="chip">${r.papers} papers</span>
        <span class="chip">${esc(capital(r.effort))} depth</span>
        <span>${esc(longDate(r.asked))}</span>
      </div>
    </a>`).join("");
  document.getElementById("view").innerHTML = `
    <header class="hero">
      <h1>Research Library</h1>
      <p class="sub" id="count">${runs.length} ${runs.length === 1 ? "report" : "reports"}, every citation checked against the arXiv corpus</p>
      <div class="searchwrap">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
        <input type="search" id="q" placeholder="Search past questions&hellip;" value="${esc(filter)}">
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
          `<option value="${n}"${n === per ? " selected" : ""}>${n > 999 ? "Show all" : n + " per page"}</option>`).join("")}
      </select>
    </div>
    <div class="grid">${cards || '<p class="empty">No past question matches that.</p>'}</div>`;

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
  const links = document.getElementById("panel-l");
  const body = document.getElementById("panel-b");
  body.innerHTML = '<div class="panel-msg">Loading the paper&hellip;</div>';
  let there = false;
  try { there = (await fetch(o.url, { method: "HEAD" })).ok; } catch (e) { there = false; }
  const shown = there ? o.url : o.remote;
  links.innerHTML =
    `<a class="pill sm" target="_blank" href="${o.ext}">arXiv &#8599;</a>` +
    `<a class="pill sm" target="_blank" href="${shown}">Open in a new tab &#8599;</a>`;
  body.innerHTML = `<iframe src="${shown}"></iframe>`;
}

function openPaper(id) {
  hidePop();
  hideTip();
  const p = byId[id] || nodeById[id];
  openPanel({
    title: p ? deTeX(p.title) : "arXiv:" + id,
    meta: p ? esc([authors(p.authors), p.year || yearOf(id), p.category, id].filter(Boolean).join(" · ")) : esc(id),
    url: "pdf/" + id,
    remote: "https://arxiv.org/pdf/" + id,
    ext: "https://arxiv.org/abs/" + id,
  });
}

function roleChip(role) {
  return role ? `<span class="rolechip role-${role}">${role}</span>` : "";
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
       ${roleChip(p.role)}</div>
       ${p.abstract ? `<div class="cp-s">${esc(deTeX(p.abstract))}</div>` : ""}${buttons}`
    : `<div class="cp-m mono">arXiv:${esc(id)}</div>${buttons}`;
  const box = anchor.getBoundingClientRect();
  pop.style.left = Math.max(scrollX + 8, Math.min(box.left + scrollX, scrollX + innerWidth - 420)) + "px";
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
  hookCitations(article);
}

const SECTIONS = [
  ["about", "Overview"],
  ["facts", "What the papers show"],
  ["methods", "Methods"],
  ["active", "Current work"],
  ["open", "Open questions"],
  ["disagree", "Disagreements"],
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
  el.innerHTML = marked.parse(linkPlain(markdown));
  decorate(el);
  return el;
}

function paperLine(p, extra) {
  return `<li>
    ${roleChip(p.role || "ungraded")}
    <span class="pl-date">${esc(p.date || "")}</span>
    <a href="https://arxiv.org/abs/${p.arxiv_id}">${esc(deTeX(p.title || p.arxiv_id))}</a>
    ${extra || ""}</li>`;
}

function answerBox(text) {
  const box = document.createElement("div");
  box.className = "answer";
  box.innerHTML = `<div class="answer-k">TL;DR</div>`;
  box.append(prose(text));
  return box;
}

function reportTab() {
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

  // 1, the answer and the overview
  if (got.answer) column.append(answerBox(got.answer));
  const about = block("about", "Overview");
  about.append(prose(got.opening || "This report has no overview. Quick runs skip the written sections."));

  // 2, one tab per claim the review makes
  const facts = block("facts", "What the papers show",
    "Each tab is one claim about the field, argued from the papers behind it.");
  const claims = (got.claims || []).map((c) => ({ label: esc(c.title), ...c }));
  if (claims.length) subtabs(facts, claims, (c) => prose(`### ${c.title}\n\n${c.body}`));
  else facts.append(prose("Nothing was written for this report."));

  // 3, the methods, whose full view is its own tab
  const methods = block("methods", "Methods",
    "The methods these papers use, compared on the questions that matter here.");
  const m = got.methods || {};
  if (m.table) {
    const go = document.createElement("p");
    go.innerHTML = `<button class="ab-btn" onclick="tab('methods')">Filter and compare in the Methods tab &rarr;</button>`;
    methods.append(prose(m.table), go);
  } else methods.append(prose("No method table for this report. Quick runs skip it."));

  // 4, one tab per area and one for what has just appeared
  const active = block("active", "Current work",
    "The papers each area is built on right now, and newer papers responding to them.");
  const areas = (got.areas || []).map((a) => ({ label: esc(a.question), ...a }));
  const tabs = [...areas];
  if ((got.successors || []).length) tabs.push({ label: "Newer papers", fresh: true });
  subtabs(active, tabs, (t) => {
    const el = document.createElement("div");
    if (t.fresh) {
      el.innerHTML = `<p class="lead">Each of these cites papers above and extends, critiques or compares
        against them, so it shows up here before anyone has cited it.</p>
        <ul class="papers">${got.successors.map((s) => paperLine(
          { ...s, role: "frontier" },
          `<span class="tech">${esc(capital(s.intents.join(", ")))}, responding to ${s.reach} ${s.reach === 1 ? "paper" : "papers"} here</span>
           ${s.sentence ? `<blockquote>${esc(s.sentence)}</blockquote>` : ""}`)).join("")}</ul>`;
      hookCitations(el);
      return el;
    }
    const held = t.papers.map((id) => byId[id]).filter(Boolean);
    el.innerHTML = `<ul class="papers">${byRoleList(held, t.seed)}</ul>`;
    hookCitations(el);
    return el;
  });

  // 5, one tab per area
  const open = block("open", "Open questions",
    "Taken from the limitations and future work sections of the papers themselves.");
  const withOpen = areas.filter((a) => (a.unanswered || []).length);
  if (withOpen.length) {
    subtabs(open, withOpen, (a) => {
      const el = document.createElement("div");
      el.innerHTML = `<ul class="opens">${a.unanswered.map((q) => `<li>${linkIds(esc(q))}</li>`).join("")}</ul>`;
      hookCitations(el);
      return el;
    });
  } else open.append(prose("None of these papers had a limitations section on file."));

  // 6, one paper telling another it is wrong
  const dis = block("disagree", "Disagreements",
    "Places where one paper says another falls short, in its own words.");
  const rows = got.disputes || [];
  const list = document.createElement("div");
  list.innerHTML = rows.length
    ? `<ul class="disputes">${rows.map((d) => `<li>
        <div class="d-head"><a href="https://arxiv.org/abs/${d.by}">${esc(titleOf(d.by))}</a>
        <span class="chip">${esc(INTENTS[d.intent] || d.intent)}</span>
        <a href="https://arxiv.org/abs/${d.arxiv_id}">${esc(titleOf(d.arxiv_id))}</a></div>
        <blockquote>${esc(d.sentence)}</blockquote></li>`).join("")}</ul>`
    : '<p class="lead">No paper here disputes another.</p>';
  hookCitations(list);
  dis.append(list);

  const nav = document.createElement("nav");
  nav.className = "toc";
  nav.innerHTML = SECTIONS.map(([k, t], i) =>
    `<a href="#" data-s="s-${k}"><span class="tocn">${i + 1}</span><span>${t}</span></a>`).join("");
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

// the paper a seeded search started from leads its area, whatever the reader graded it
function byRoleList(list, seed = "") {
  const rank = (p) => (p.arxiv_id === seed ? -1 : ROLE_ORDER.indexOf(p.role || "ungraded"));
  return [...list]
    .sort((a, b) => rank(a) - rank(b))
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

// -- methods ---------------------------------------------------------------------------------

let methodData = null;
let methodPicks = {};
let methodQuery = "";
let methodSort = { key: "year", dir: -1 };
let crossA = "";
let crossB = "";

const NA = (v) => !v || /^(n\/?a|none|unknown|-)$/i.test(String(v).trim());
const axisLabel = (name) => capital(String(name).replace(/_/g, " "));

// an older run carries the table only as markdown, so the rows are read back out of it
function readMethods(m) {
  if ((m.rows || []).length && (m.columns || []).length) {
    return { columns: m.columns, rows: m.rows };
  }
  const lines = String(m.table || "").split("\n").filter((l) => l.trim().startsWith("|"));
  if (lines.length < 3) return null;
  const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  const head = cells(lines[0]);
  const names = head.slice(2, -1);
  const described = {};
  for (const found of String(m.spread || "").matchAll(/\*\*([^*]+)\*\*, ([^\n]+)/g)) described[found[1]] = found[2];
  // the spread only lists the columns that group, so a column missing from it is free text
  const columns = names.map((n) => ({ name: n, kind: n in described ? "choice" : "text", description: described[n] || "", options: [] }));
  const rows = lines.slice(2).map((l) => {
    const c = cells(l);
    return {
      name: c[0],
      year: c[1],
      values: Object.fromEntries(names.map((n, i) => [n, c[i + 2] || ""])),
      papers: [...(c[c.length - 1] || "").matchAll(/(\d{4}\.\d{4,5}|[a-z][a-z.\-]+\/\d{7})/g)].map((x) => x[1]),
    };
  });
  return { columns, rows };
}

// a run written before columns carried their kind still lists options for exactly the ones that group
const grouped = (c) => (c.kind ? c.kind === "choice" : (c.options || []).length >= 2);

function optionsOf(column) {
  const seen = new Map();
  for (const o of column.options || []) seen.set(o, 0);
  for (const r of methodData.rows) {
    const v = r.values[column.name];
    if (!NA(v)) seen.set(v, (seen.get(v) || 0) + 1);
  }
  return [...seen.entries()].sort((a, b) => b[1] - a[1]);
}

function methodShown() {
  return methodData.rows.filter((r) => {
    for (const [axis, picked] of Object.entries(methodPicks)) {
      if (picked.size && !picked.has(r.values[axis])) return false;
    }
    if (methodQuery) {
      const hay = `${r.name} ${Object.values(r.values).join(" ")}`.toLowerCase();
      if (!hay.includes(methodQuery)) return false;
    }
    return true;
  });
}

function methodsTab() {
  const host = document.getElementById("p-methods");
  methodData = readMethods((run.sections || {}).methods || {});
  if (!methodData || !methodData.rows.length) {
    host.innerHTML = '<p class="empty">No method table for this report. Quick runs skip it.</p>';
    return;
  }
  methodPicks = {};
  methodQuery = "";
  const axes = methodData.columns.filter(grouped);
  crossA = axes[0]?.name || "";
  crossB = axes[1]?.name || crossA;
  host.innerHTML = `
    <p class="lead mlead">Each row is one method, and each column is a question the methods answer
      differently. Click a value to show only the methods that share it.</p>
    <div class="mwrap">
      <aside class="mfilters" id="mfilters"></aside>
      <div class="mmain">
        <div class="rtools">
          <input type="search" id="mq" placeholder="Search methods&hellip;">
          <button class="pill sm" id="mclear">Clear filters</button>
          <span class="byline" id="mcount"></span>
        </div>
        <div class="tablewrap"><table class="mtable" id="mtable"></table></div>
        <h3 class="mh">Combinations nobody has tried</h3>
        <p class="lead">Pick two questions. Each cell counts the methods that combine the two answers, and an empty cell is a combination no paper here tried.</p>
        <div class="rtools">
          <select class="pill sm" id="xa"></select><span class="byline">against</span><select class="pill sm" id="xb"></select>
        </div>
        <div class="tablewrap" id="mcross"></div>
      </div>
    </div>`;
  const pick = (id, current) => methodData.columns.filter(grouped).map((c) =>
    `<option value="${esc(c.name)}"${c.name === current ? " selected" : ""}>${esc(axisLabel(c.name))}</option>`).join("");
  document.getElementById("xa").innerHTML = pick("xa", crossA);
  document.getElementById("xb").innerHTML = pick("xb", crossB);
  document.getElementById("xa").onchange = (e) => { crossA = e.target.value; drawCross(); };
  document.getElementById("xb").onchange = (e) => { crossB = e.target.value; drawCross(); };
  document.getElementById("mq").oninput = (e) => { methodQuery = e.target.value.toLowerCase(); drawMethods(); };
  document.getElementById("mclear").onclick = () => {
    methodPicks = {};
    methodQuery = "";
    document.getElementById("mq").value = "";
    drawMethods();
  };
  drawMethods();
}

function toggleMethod(axis, value) {
  if (!methodPicks[axis]) methodPicks[axis] = new Set();
  const held = methodPicks[axis];
  if (held.has(value)) held.delete(value); else held.add(value);
  drawMethods();
}

function drawMethods() {
  const shown = methodShown();
  const total = methodData.rows.length;
  // the filter chips count what the other filters leave, so a zero means that choice empties the table
  document.getElementById("mfilters").innerHTML = methodData.columns.filter(grouped).map((c) => {
    const options = optionsOf(c);
    const most = Math.max(1, ...options.map(([, n]) => n));
    return `<div class="mgroup">
      <div class="mgroup-t">${esc(axisLabel(c.name))}</div>
      ${c.description ? `<div class="mgroup-d">${esc(capital(c.description))}</div>` : ""}
      ${options.map(([v, n]) => {
        const on = methodPicks[c.name] && methodPicks[c.name].has(v);
        return `<button class="mchip${on ? " on" : ""}${n ? "" : " zero"}" data-a="${esc(c.name)}" data-v="${esc(v)}">
          <span>${esc(v)}</span><b>${n}</b><i style="width:${(100 * n) / most}%"></i></button>`;
      }).join("")}
    </div>`;
  }).join("");
  for (const b of document.querySelectorAll(".mchip")) b.onclick = () => toggleMethod(b.dataset.a, b.dataset.v);

  const key = methodSort.key;
  const sorted = [...shown].sort((a, b) => {
    const x = key === "name" ? a.name : key === "year" ? a.year : a.values[key] || "";
    const y = key === "name" ? b.name : key === "year" ? b.year : b.values[key] || "";
    return String(x).localeCompare(String(y), undefined, { numeric: true }) * methodSort.dir;
  });
  const arrow = (k) => (methodSort.key === k ? (methodSort.dir > 0 ? " &uarr;" : " &darr;") : "");
  const heads = [["name", "Method"], ["year", "Year"], ...methodData.columns.map((c) => [c.name, axisLabel(c.name)])];
  const table = document.getElementById("mtable");
  table.innerHTML = `<thead><tr>${heads.map(([k, l]) =>
      `<th data-k="${esc(k)}" title="Sort by this column">${esc(l)}${arrow(k)}</th>`).join("")}<th>Papers</th></tr></thead>
    <tbody>${sorted.map((r) => `<tr>
      <td>${esc(r.name)}</td><td class="mono">${esc(r.year)}</td>
      ${methodData.columns.map((c) => {
        const v = r.values[c.name];
        if (NA(v)) return '<td><span class="tech">not stated</span></td>';
        if (!grouped(c)) return `<td class="mfree">${esc(v)}</td>`;
        const on = methodPicks[c.name] && methodPicks[c.name].has(v);
        return `<td><button class="mval${on ? " on" : ""}" data-a="${esc(c.name)}" data-v="${esc(v)}">${esc(v)}</button></td>`;
      }).join("")}
      <td>${r.papers.map((id) => `<a class="mono" href="https://arxiv.org/abs/${id}">${id}</a>`).join("<br>")}</td>
    </tr>`).join("") || `<tr><td colspan="${heads.length + 1}" class="tech">No method matches every filter.</td></tr>`}</tbody>`;
  for (const th of table.querySelectorAll("th[data-k]")) {
    th.onclick = () => {
      const k = th.dataset.k;
      methodSort = { key: k, dir: methodSort.key === k ? -methodSort.dir : 1 };
      drawMethods();
    };
  }
  for (const b of table.querySelectorAll(".mval")) b.onclick = () => toggleMethod(b.dataset.a, b.dataset.v);
  hookCitations(table);
  document.getElementById("mcount").textContent = shown.length === total
    ? `${total} methods` : `${shown.length} of ${total} methods`;
  drawCross();
}

function drawCross() {
  const host = document.getElementById("mcross");
  const a = methodData.columns.find((c) => c.name === crossA);
  const b = methodData.columns.find((c) => c.name === crossB);
  if (!a || !b || a === b) {
    host.innerHTML = '<p class="tech" style="padding:12px">Pick two different questions.</p>';
    return;
  }
  const rowsA = optionsOf(a).map(([v]) => v);
  const colsB = optionsOf(b).map(([v]) => v);
  const count = (x, y) => methodData.rows.filter((r) => r.values[a.name] === x && r.values[b.name] === y).length;
  const most = Math.max(1, ...rowsA.flatMap((x) => colsB.map((y) => count(x, y))));
  host.innerHTML = `<table class="mcross"><thead><tr><th></th>${colsB.map((y) => `<th>${esc(y)}</th>`).join("")}</tr></thead>
    <tbody>${rowsA.map((x) => `<tr><th>${esc(x)}</th>${colsB.map((y) => {
      const n = count(x, y);
      return n
        ? `<td class="hit" style="--k:${(0.15 + (0.6 * n) / most).toFixed(2)}" data-x="${esc(x)}" data-y="${esc(y)}" title="Show these ${n}">${n}</td>`
        : '<td class="gap" title="No paper here combines these">none</td>';
    }).join("")}</tr>`).join("")}</tbody></table>`;
  for (const td of host.querySelectorAll("td.hit")) {
    td.onclick = () => {
      methodPicks = { [a.name]: new Set([td.dataset.x]), [b.name]: new Set([td.dataset.y]) };
      drawMethods();
      document.getElementById("mtable").scrollIntoView({ block: "start" });
    };
  }
}

// -- references ------------------------------------------------------------------------------

const REF_DEFAULT = () => ({
  query: "", roles: new Set(), cited: "all", found: "all", area: "", line: "", from: "", to: "",
  category: "", sort: "relevance",
});
let refs = REF_DEFAULT();

function refItem(p) {
  const node = nodeById[p.arxiv_id] || {};
  const meta = [authors(p.authors), p.year, p.category].filter(Boolean).join(" · ");
  const facts = [
    node.cited_by != null ? `cited ${node.cited_by.toLocaleString()} times` : "",
    p.cosine != null ? `closeness ${p.cosine.toFixed(2)}` : "",
    ...(node.lines || []).map((n) => `on ${esc(lineName(n))}`),
  ].filter(Boolean).join(" · ");
  return `<div class="ref">
    <div class="ref-main">
      <div class="ref-t"><a href="https://arxiv.org/abs/${p.arxiv_id}">${esc(deTeX(p.title))}</a>${p.cited ? '<span class="cited-b">CITED</span>' : ""}</div>
      <div class="ref-m">${esc(meta)}${roleChip(p.role)}${p.retrieved ? "" : '<span class="chip">found through citations</span>'}</div>
      <div class="tech">${esc(p.arxiv_id)}${facts ? " · " + facts : ""}</div>
      ${p.abstract ? `<p class="ref-s">${esc(deTeX(p.abstract))}</p>` : ""}
    </div>
    <div class="ref-side">
      <button class="pill sm" onclick="openPaper('${p.arxiv_id}')">Read</button>
      <a class="pill sm" target="_blank" href="https://arxiv.org/abs/${p.arxiv_id}">arXiv &#8599;</a>
    </div></div>`;
}

function refMatches(p) {
  const node = nodeById[p.arxiv_id] || {};
  const role = p.role || (p.retrieved ? "ungraded" : "connector");
  if (refs.roles.size && !refs.roles.has(role)) return false;
  if (refs.cited === "cited" && !p.cited) return false;
  if (refs.cited === "uncited" && p.cited) return false;
  if (refs.found === "search" && !p.retrieved) return false;
  if (refs.found === "graph" && p.retrieved) return false;
  if (refs.area !== "") {
    const area = (run.areas || [])[+refs.area];
    if (!area || !area.papers.includes(p.arxiv_id)) return false;
  }
  if (refs.line === "any" && !(node.lines || []).length) return false;
  if (refs.line && refs.line !== "any" && !(node.lines || []).includes(+refs.line)) return false;
  if (refs.from && String(p.year) < refs.from) return false;
  if (refs.to && String(p.year) > refs.to) return false;
  if (refs.category && p.category !== refs.category) return false;
  if (refs.query && !`${p.title} ${p.authors} ${p.abstract} ${p.arxiv_id}`.toLowerCase().includes(refs.query)) return false;
  return true;
}

function referencesTab() {
  const host = document.getElementById("p-references");
  if (!papers.length) { host.innerHTML = '<p class="empty">This report recorded no papers.</p>'; return; }
  const years = [...new Set(papers.map((p) => String(p.year)).filter(Boolean))].sort();
  const cats = Object.entries(papers.reduce((o, p) => ((o[p.category] = (o[p.category] || 0) + 1), o), {}))
    .filter(([c]) => c && c !== "undefined").sort((a, b) => b[1] - a[1]);
  const roles = ROLE_ORDER.filter((r) => papers.some((p) => (p.role || (p.retrieved ? "ungraded" : "connector")) === r));
  const lines = ((run.sections || {}).lineages || []).map((_, i) => i + 1);
  const opt = (v, l, cur) => `<option value="${esc(v)}"${String(v) === String(cur) ? " selected" : ""}>${esc(l)}</option>`;
  const seg = (name, items) => `<span class="seg" data-f="${name}">${items.map(([v, l]) =>
    `<button class="${refs[name] === v ? "on" : ""}" data-v="${v}">${l}</button>`).join("")}</span>`;
  host.innerHTML = `
    <div class="rtools">
      <input type="search" id="rq" placeholder="Search titles, authors and abstracts&hellip;" value="${esc(refs.query)}">
      <select class="pill sm" id="rsort">
        ${[["relevance", "Most relevant"], ["new", "Newest"], ["old", "Oldest"], ["cosine", "Closest to the question"],
          ["cited_by", "Most cited"]].map(([v, l]) => opt(v, l, refs.sort)).join("")}
      </select>
      <button class="pill sm" id="rclear">Clear filters</button>
      <span class="byline" id="rcount"></span>
    </div>
    <div class="rfilters">
      <div class="rf"><span class="rf-k">Role</span><span class="rf-v">${roles.map((r) =>
        `<button class="grole${refs.roles.has(r) ? " picked" : ""}" data-role="${r}"><i class="role-dot role-${r}"></i>${r}</button>`).join("")}</span></div>
      <div class="rf"><span class="rf-k">In the report</span>${seg("cited", [["all", "Any"], ["cited", "Cited"], ["uncited", "Not cited"]])}</div>
      <div class="rf"><span class="rf-k">Found by</span>${seg("found", [["all", "Either"], ["search", "The search"], ["graph", "Following citations"]])}</div>
      <div class="rf"><span class="rf-k">Area</span><select class="pill sm" id="rarea">${opt("", "Every area", refs.area)}${(run.areas || []).map((a, i) =>
        opt(i, a.question.length > 70 ? a.question.slice(0, 68) + "..." : a.question, refs.area)).join("")}</select></div>
      <div class="rf"><span class="rf-k">Line</span><select class="pill sm" id="rline">${opt("", "Any paper", refs.line)}${opt("any", "On any line", refs.line)}${lines.map((n) =>
        opt(n, lineName(n), refs.line)).join("")}</select></div>
      <div class="rf"><span class="rf-k">Published</span><select class="pill sm" id="rfrom">${opt("", "From any year", refs.from)}${years.map((y) =>
        opt(y, "From " + y, refs.from)).join("")}</select><select class="pill sm" id="rto">${opt("", "To any year", refs.to)}${years.map((y) =>
        opt(y, "To " + y, refs.to)).join("")}</select></div>
      <div class="rf"><span class="rf-k">Category</span><select class="pill sm" id="rcat">${opt("", "Any category", refs.category)}${cats.map(([c, n]) =>
        opt(c, `${c} (${n})`, refs.category)).join("")}</select></div>
    </div>
    <div class="reflist" id="reflist"></div>`;

  const box = document.getElementById("rq");
  box.oninput = (e) => { refs.query = e.target.value.toLowerCase(); drawRefs(); };
  document.getElementById("rsort").onchange = (e) => { refs.sort = e.target.value; drawRefs(); };
  document.getElementById("rclear").onclick = () => { refs = REF_DEFAULT(); referencesTab(); };
  for (const b of host.querySelectorAll(".rf .grole")) {
    b.onclick = () => {
      const r = b.dataset.role;
      if (refs.roles.has(r)) refs.roles.delete(r); else refs.roles.add(r);
      b.classList.toggle("picked");
      drawRefs();
    };
  }
  for (const s of host.querySelectorAll(".seg")) {
    for (const b of s.children) {
      b.onclick = () => {
        refs[s.dataset.f] = b.dataset.v;
        for (const o of s.children) o.classList.toggle("on", o === b);
        drawRefs();
      };
    }
  }
  const bind = (id, key) => { document.getElementById(id).onchange = (e) => { refs[key] = e.target.value; drawRefs(); }; };
  bind("rarea", "area");
  bind("rline", "line");
  bind("rfrom", "from");
  bind("rto", "to");
  bind("rcat", "category");
  drawRefs();
}

function drawRefs() {
  let shown = papers.filter(refMatches);
  const cited = (p) => (nodeById[p.arxiv_id] || {}).cited_by ?? -1;
  const s = refs.sort;
  shown = [...shown].sort((a, b) =>
    s === "relevance" ? (b.relevance ?? -9) - (a.relevance ?? -9) || (b.cosine ?? 0) - (a.cosine ?? 0)
    : s === "new" ? String(b.date).localeCompare(String(a.date))
    : s === "old" ? String(a.date).localeCompare(String(b.date))
    : s === "cited_by" ? cited(b) - cited(a)
    : (b[s] ?? -1e9) - (a[s] ?? -1e9));
  const list = document.getElementById("reflist");
  list.innerHTML = shown.map(refItem).join("") || '<p class="empty">No paper matches every filter.</p>';
  hookCitations(list);
  document.getElementById("rcount").textContent =
    `${shown.length} of ${papers.length} papers, ${shown.filter((p) => p.cited).length} cited in the report`;
}

// -- the graph -------------------------------------------------------------------------------

let hiddenRoles = new Set();
// the two most common intents bury the rest, so they start hidden
let hiddenIntents = new Set(["background", "uses"]);
let pickedLine = 1;
let focusedNode = null;

const linesOf = () => ((run.sections || {}).lineages || []).map((l, i) => ({ n: i + 1, ...l }));

// the citations between one line's own papers, which older runs did not store with the line
function lineEdges(line) {
  const held = new Set(line.papers.map((p) => p.arxiv_id));
  const all = line.edges || ((run.graph || {}).edges || []).filter((e) => held.has(e.source) && held.has(e.target));
  // a paper that cites another three times in its text is still one citation between them
  const seen = new Map();
  for (const e of all) {
    const k = `${e.source}|${e.target}|${e.intent}`;
    if (!seen.has(k)) seen.set(k, e);
  }
  return [...seen.values()];
}

function intentChips(edges) {
  const counted = {};
  for (const e of edges) counted[e.intent] = (counted[e.intent] || 0) + 1;
  const order = Object.keys(INTENTS).filter((i) => counted[i]);
  if (!order.length) return '<span class="tech">no citations between its papers</span>';
  return order.map((i) => `<span class="ichip"><i class="idot intent-${i}"></i>${counted[i]} ${esc(INTENTS[i])}</span>`).join("");
}

function graphTab() {
  const graph = run.graph;
  const host = document.getElementById("p-graph");
  if (!graph || !graph.nodes || !graph.nodes.length) {
    host.innerHTML = '<p class="empty">This report has no graph.</p>';
    return;
  }
  const roles = ROLE_ORDER.filter((r) => graph.nodes.some((n) => n.role === r));
  const intents = Object.keys(INTENTS).filter((i) => graph.edges.some((e) => e.intent === i));
  const tally = (i) => graph.edges.filter((e) => e.intent === i).length;
  const lines = linesOf();
  if (pickedLine > lines.length) pickedLine = lines.length ? 1 : 0;
  const cur = lines[pickedLine - 1];
  host.innerHTML = `
    ${lines.length ? `<div class="glinetabs" role="tablist">${lines.map((l) =>
      `<button class="glt${l.n === pickedLine ? " on" : ""}" data-n="${l.n}" style="--c:${lineColor(l.n)}"><i></i>${esc(lineName(l.n))}</button>`).join("")}
      <button class="glt${pickedLine ? "" : " on"}" data-n="0">No line</button></div>` : ""}
    ${cur ? `<div class="glinehead" style="--c:${lineColor(cur.n)}">
      <div class="glh-t">Line ${cur.n} &middot; ${cur.papers.length} papers, ${cur.papers[0]?.date.slice(0, 4)} to ${cur.papers[cur.papers.length - 1]?.date.slice(0, 4)}, found by ${cur.runs} ${cur.runs === 1 ? "walk" : "walks"}</div>
      ${cur.description ? `<p>${esc(cur.description)}</p>` : ""}
      <div class="ichips">${intentChips(lineEdges(cur))}</div></div>` : ""}
    <div class="gpanel">
      <div class="gfield"><span class="rf-k">Roles</span>
        <span class="glegend">${roles.map((r) =>
          `<button class="grole${hiddenRoles.has(r) ? " off" : ""}" data-r="${r}"><i class="role-dot role-${r}"></i>${r}</button>`).join("")}</span></div>
      <div class="gfield"><span class="rf-k">Citations</span>
        <span class="glegend">${intents.map((i) =>
          `<button class="grole${hiddenIntents.has(i) ? " off" : ""}" data-i="${i}"><i class="idot intent-${i}"></i>${INTENTS[i]} <span class="tech">${tally(i)}</span></button>`).join("")}</span></div>
      <div class="gfield"><span class="rf-k">Find</span><input type="search" id="gq" placeholder="A title or an arXiv id&hellip;"></div>
    </div>
    <div class="gwrap" id="gwrap"></div>
    <p class="byline gcap">Older papers sit left and papers closer to the question sit higher. A bigger dot is cited more.
      The picked line is drawn in its color with every citation between its papers, whatever the filters above hide.
      Hover a dot or a citation to see what it is, and click to open the paper.</p>
    <div id="paths"></div>`;
  for (const b of host.querySelectorAll(".grole[data-r]")) {
    b.onclick = () => {
      const r = b.dataset.r;
      if (hiddenRoles.has(r)) hiddenRoles.delete(r); else hiddenRoles.add(r);
      graphTab();
    };
  }
  for (const b of host.querySelectorAll(".grole[data-i]")) {
    b.onclick = () => {
      const i = b.dataset.i;
      if (hiddenIntents.has(i)) hiddenIntents.delete(i); else hiddenIntents.add(i);
      graphTab();
    };
  }
  for (const b of host.querySelectorAll(".glt")) b.onclick = () => { pickedLine = +b.dataset.n; graphTab(); };
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
  const lines = linesOf();
  if (!lines.length) { host.innerHTML = ""; return; }
  host.innerHTML = `<h3 class="pathh">Every line through this field</h3>` + lines.map((line) => {
    const edges = lineEdges(line);
    const first = line.papers[0]?.date.slice(0, 4);
    const last = line.papers[line.papers.length - 1]?.date.slice(0, 4);
    const at = Object.fromEntries(line.papers.map((p, i) => [p.arxiv_id, i]));
    const steps = line.papers.map((p, i) => {
      const out = edges.filter((e) => e.source === p.arxiv_id && at[e.target] != null)
        .sort((a, b) => at[b.target] - at[a.target]);
      const into = edges.filter((e) => e.target === p.arxiv_id && at[e.source] != null && at[e.source] < i);
      const said = [
        ...out.map((e) => `<span class="ichip" title="${esc(e.sentence || "")}"><i class="idot intent-${e.intent}"></i>${esc(INTENTS[e.intent] || e.intent)} ${esc(yearOf(e.target))} &ldquo;${esc(titleOf(e.target).slice(0, 38))}&rdquo;</span>`),
        ...into.map((e) => `<span class="ichip back" title="${esc(e.sentence || "")}"><i class="idot intent-${e.intent}"></i>cited by ${esc(yearOf(e.source))} as ${esc(e.intent)}</span>`),
      ].join("");
      return `<li><span class="pl-date">${p.date}</span>
        <div><a href="https://arxiv.org/abs/${p.arxiv_id}">${esc(deTeX(p.title))}</a>
        ${said ? `<div class="stepcites">${said}</div>` : ""}</div></li>`;
    }).join("");
    return `<details class="path" style="--c:${lineColor(line.n)}">
      <summary class="pathtop">
        <div class="pt-row"><i class="pathdot"></i><b>${esc(lineName(line.n))}</b>
          <span class="tech">${line.papers.length} papers, ${first} to ${last}</span>
          <button class="pill sm pt-show" data-n="${line.n}">${pickedLine === line.n ? "On the chart" : "Show on the chart"}</button></div>
        ${line.description ? `<p class="pdesc">${esc(line.description)}</p>` : ""}
        <div class="ichips">${intentChips(edges)}</div>
      </summary>
      <ol class="pathsteps">${steps}</ol>
    </details>`;
  }).join("");
  for (const b of host.querySelectorAll(".pt-show")) {
    b.onclick = (e) => {
      e.preventDefault();
      pickedLine = +b.dataset.n;
      graphTab();
      document.getElementById("gwrap").scrollIntoView({ block: "center" });
    };
  }
  hookCitations(host);
}

let tip = null;
function hideTip() { if (tip) tip.style.display = "none"; }

function showTip(e, html) {
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "gtip";
    document.body.append(tip);
  }
  tip.innerHTML = html;
  tip.style.display = "block";
  const w = tip.offsetWidth;
  const h = tip.offsetHeight;
  let x = e.clientX + 16;
  let y = e.clientY + 16;
  if (x + w > innerWidth - 8) x = e.clientX - w - 16;
  if (y + h > innerHeight - 8) y = Math.max(8, e.clientY - h - 16);
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}

function nodeTip(n) {
  const p = byId[n.arxiv_id] || {};
  const facts = [
    `${n.cited_by.toLocaleString()} citations`,
    n.cosine != null ? `closeness ${n.cosine.toFixed(2)}` : "",
  ].filter(Boolean).join(" · ");
  return `<div class="cp-t">${esc(deTeX(n.title))}</div>
    <div class="cp-m">${esc(authors(p.authors))}${p.authors ? " · " : ""}${esc(longDate(n.date))} ${roleChip(n.role)}</div>
    <div class="cp-m">${facts}</div>
    ${n.lines.length ? `<div class="gtip-lines">${n.lines.map((l) =>
      `<span style="--c:${lineColor(l)}"><i></i>${esc(lineName(l))}</span>`).join("")}</div>` : ""}
    ${p.abstract ? `<div class="cp-s">${esc(deTeX(p.abstract))}</div>` : ""}`;
}

function edgeTip(e) {
  return `<div class="gtip-edge"><b>${esc(titleOf(e.source))}</b> <span class="tech">${yearOf(e.source)}</span></div>
    <div class="gtip-verb intent-${e.intent}">${esc(INTENTS[e.intent] || e.intent)}</div>
    <div class="gtip-edge"><b>${esc(titleOf(e.target))}</b> <span class="tech">${yearOf(e.target)}</span></div>
    ${e.sentence ? `<blockquote>${esc(e.sentence.replace(/\[CITE\]/g, "[this paper]"))}</blockquote>` : ""}`;
}

function drawGraph(graph) {
  const host = document.getElementById("gwrap");
  const lineRows = ((run.sections || {}).lineages || []);
  const cur = linesOf()[pickedLine - 1];
  const onLine = new Set(cur ? cur.papers.map((p) => p.arxiv_id) : []);
  const shown = graph.nodes.filter((n) => !hiddenRoles.has(n.role) || onLine.has(n.arxiv_id));
  if (!shown.length) { host.innerHTML = '<p class="empty">Every role is hidden.</p>'; return; }
  const held = new Set(shown.map((n) => n.arxiv_id));
  const at = shown.map((n) => Date.parse(n.date));
  const cos = shown.map((n) => n.cosine ?? 0);
  const t0 = Math.min(...at);
  const t1 = Math.max(Math.max(...at), t0 + 8.64e7);
  const c0 = Math.min(...cos);
  const c1 = Math.max(Math.max(...cos), c0 + 0.01);
  const years = (t1 - t0) / 3.156e10;
  // the whole span has to be visible without scrolling, since the paths are read left to right
  const room = host.clientWidth || 1100;
  const tight = room < 560;
  const pad = { l: tight ? 40 : 66, r: tight ? 14 : 30, t: 22, b: 52 };
  const floor = Math.min(900, room - 2);
  const width = Math.max(floor, Math.min(room - 2, Math.round(years * 150) + pad.l + pad.r));
  const height = tight ? 420 : 620;
  const X = (d) => pad.l + ((Date.parse(d) - t0) / (t1 - t0)) * (width - pad.l - pad.r);
  const Y = (c) => pad.t + (1 - ((c ?? 0) - c0) / (c1 - c0)) * (height - pad.t - pad.b);
  const R = (n) => 3.5 + 7 * Math.sqrt(Math.min(1, (n.cited_by || 0) / 400));
  const byId2 = Object.fromEntries(shown.map((n) => [n.arxiv_id, n]));

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
  grid.push(`<text class="gaxis" x="${width / 2}" y="${height - 12}" text-anchor="middle">published &rarr;</text>`);
  grid.push(`<text class="gaxis" transform="translate(${tight ? 11 : 16} ${height / 2}) rotate(-90)" text-anchor="middle">${tight ? "closeness &rarr;" : "closeness to the question &rarr;"}</text>`);

  const edges = graph.edges
    .map((e, i) => ({ ...e, i }))
    .map((e) => ({ ...e, inline: onLine.has(e.source) && onLine.has(e.target) }))
    .filter((e) => held.has(e.source) && held.has(e.target) && (e.inline || !hiddenIntents.has(e.intent)));
  const edgeSvg = edges.map((e) => {
    const a = byId2[e.source];
    const b = byId2[e.target];
    const d = `x1="${X(a.date)}" y1="${Y(a.cosine)}" x2="${X(b.date)}" y2="${Y(b.cosine)}"`;
    return `<g class="gedge-g${e.inline ? " inline" : ""}" data-e="${e.i}" data-s="${e.source}" data-t="${e.target}">
      <line class="gedge intent-${e.intent}" ${d}/><line class="ghit" ${d}/></g>`;
  }).join("");

  // each line is drawn through its own papers in order, in its own color
  const drawn = lineRows.map((l, i) => ({ n: i + 1, ...l })).filter((l) => l.n === pickedLine);
  const lineSvg = drawn.map((l) => {
    const pts = l.papers.filter((p) => held.has(p.arxiv_id)).map((p) => `${X(p.date)},${Y(byId2[p.arxiv_id].cosine)}`);
    if (pts.length < 2) return "";
    return `<g class="gline-g" data-l="${l.n}"><polyline class="gpath" points="${pts.join(" ")}" style="stroke:${lineColor(l.n)}"/>
      <polyline class="ghit" points="${pts.join(" ")}"/></g>`;
  }).join("");

  const dots = shown.map((n) => {
    const on = onLine.has(n.arxiv_id);
    return `<g class="gnode${cur && !on ? " dim" : ""}" data-id="${n.arxiv_id}">
      <circle class="role-fill role-${n.role}" cx="${X(n.date)}" cy="${Y(n.cosine)}" r="${R(n)}"
        stroke="${on ? lineColor(pickedLine) : "var(--mantle)"}" stroke-width="${on ? 2.5 : 1}"/>
    </g>`;
  }).join("");

  const placed = [];
  const labels = shown
    .filter((n) => (pickedLine ? n.lines.includes(pickedLine) : n.cited_by > 0))
    .sort((a, b) => (b.cited_by || 0) - (a.cited_by || 0))
    .map((n) => {
      const x = X(n.date) + R(n) + 6;
      const y = Y(n.cosine) + 4;
      const cut = tight ? 16 : 30;
      if (placed.some((p) => Math.abs(p.y - y) < (tight ? 24 : 13) && Math.abs(p.x - x) < cut * 7)) return "";
      placed.push({ x, y });
      return `<text class="glabel" data-id="${n.arxiv_id}" x="${x}" y="${y}">${esc(deTeX(n.title).slice(0, cut))}</text>`;
    })
    .filter(Boolean)
    .slice(0, tight ? 4 : 18)
    .join("");

  host.innerHTML = `<svg width="${width}" height="${height}" role="img" id="gsvg"${cur ? ' class="picked"' : ""}>
    ${grid.join("")}<g class="gedges">${edgeSvg}</g><g class="glines">${lineSvg}</g>${dots}${labels}</svg>`;
  wireGraph(graph, edges);
  if (focusedNode) spotlight(focusedNode);
}

// hovering lights up what a paper cites and what cites it, and dims the rest
function spotlight(id, only) {
  const svg = document.getElementById("gsvg");
  if (!svg) return;
  const near = new Set([id]);
  for (const g of svg.querySelectorAll(".gedge-g")) {
    const hit = only ? g === only : g.dataset.s === id || g.dataset.t === id;
    g.classList.toggle("hi", hit);
    if (hit) { near.add(g.dataset.s); near.add(g.dataset.t); }
  }
  for (const g of svg.querySelectorAll(".gnode")) g.classList.toggle("hi", near.has(g.dataset.id));
  for (const t of svg.querySelectorAll(".glabel")) t.classList.toggle("hi", near.has(t.dataset.id));
  svg.classList.add("focus");
}

function unspot() {
  const svg = document.getElementById("gsvg");
  if (!svg) return;
  svg.classList.remove("focus");
  for (const el of svg.querySelectorAll(".hi")) el.classList.remove("hi");
  if (focusedNode) spotlight(focusedNode);
}

function wireGraph(graph, edges) {
  const svg = document.getElementById("gsvg");
  const nodes = Object.fromEntries(graph.nodes.map((n) => [n.arxiv_id, n]));
  const byIndex = Object.fromEntries(edges.map((e) => [e.i, e]));
  for (const g of svg.querySelectorAll(".gnode")) {
    const n = nodes[g.dataset.id];
    g.onmouseenter = (e) => { spotlight(n.arxiv_id); showTip(e, nodeTip(n)); };
    g.onmousemove = (e) => showTip(e, nodeTip(n));
    g.onmouseleave = () => { unspot(); hideTip(); };
    g.onclick = () => openPaper(n.arxiv_id);
  }
  for (const g of svg.querySelectorAll(".gedge-g")) {
    const e = byIndex[g.dataset.e];
    g.onmouseenter = (ev) => { spotlight(e.source, g); showTip(ev, edgeTip(e)); };
    g.onmousemove = (ev) => showTip(ev, edgeTip(e));
    g.onmouseleave = () => { unspot(); hideTip(); };
    g.onclick = () => openPaper(e.source);
  }
  const lineRows = (run.sections || {}).lineages || [];
  for (const g of svg.querySelectorAll(".gline-g")) {
    const n = +g.dataset.l;
    const l = lineRows[n - 1];
    const html = `<div class="gtip-lines"><span style="--c:${lineColor(n)}"><i></i><b>${esc(lineName(n))}</b></span></div>
      <div class="cp-m">${l.papers.length} papers from ${l.papers[0].date.slice(0, 4)} to ${l.papers[l.papers.length - 1].date.slice(0, 4)}</div>
      <ol class="gtip-steps">${l.papers.map((p) => `<li><span class="pl-date">${p.date.slice(0, 4)}</span> ${esc(deTeX(p.title))}</li>`).join("")}</ol>
      ${l.description ? `<div class="cp-s">${esc(l.description)}</div>` : ""}
      <div class="ichips">${intentChips(lineEdges({ n, ...l }))}</div>`;
    g.onmouseenter = (e) => { g.classList.add("hi"); svg.classList.add("focus-line"); showTip(e, html); };
    g.onmousemove = (e) => showTip(e, html);
    g.onmouseleave = () => { g.classList.remove("hi"); svg.classList.remove("focus-line"); hideTip(); };
  }
}

// -- details ---------------------------------------------------------------------------------

const COUNT_WORDS = {
  queries: "Searches",
  papers: "Papers kept",
  union: "Papers after following their references",
  edges: "Citations between them",
  lineages: "Lines found",
  successors: "Newer papers responding to them",
};
const TIME_WORDS = {
  "retrieve and read": "Searching and grading papers",
  "mine and write": "Reading citations and writing",
};

function detailsTab() {
  const counts = run.counts || {};
  const seconds = run.seconds || {};
  const row = (k, v) => `<div class="drow"><span>${esc(k)}</span><span>${esc(v)}</span></div>`;
  const sec = run.sections || {};
  const kept = { lineages: (sec.lineages || []).length, successors: (sec.successors || []).length };
  const countRows = Object.entries(counts).filter(([k]) => k !== "magnets").map(([k, v]) => row(COUNT_WORDS[k] || capital(k),
    Number(v).toLocaleString() + (k in kept && kept[k] < v ? `, ${kept[k]} shown` : ""))).join("");
  const total = Object.values(seconds).reduce((a, b) => a + b, 0);
  const timeRows = Object.entries(seconds).map(([k, v]) => row(TIME_WORDS[k] || capital(k), duration(v))).join("")
    + (total ? row("Total", duration(total)) : "");
  const areas = (run.areas || []).map((a) =>
    `<div class="drow"><span>${esc(a.question)}</span><span>${a.papers.length} papers</span></div>`).join("");
  const fixed = Object.keys(run.corrected || {}).length;
  const cut = (run.cut || []).length;
  document.getElementById("p-details").innerHTML = `<div class="dgrid">
    <div class="dcard"><h3>Paper counts</h3>${countRows || row("Nothing recorded", "")}</div>
    <div class="dcard"><h3>Time</h3>${timeRows || row("Nothing recorded", "")}</div>
    <div class="dcard"><h3>Citation check</h3>
      ${row("Citations verified", (run.cited || []).length)}
      ${row("Mistyped ids fixed", fixed)}
      ${row("Made-up ids removed", cut)}
      <p class="tech dnote">Every arXiv id in the report is looked up in the corpus before it is saved.</p></div>
    <div class="dcard"><h3>Areas searched</h3>${areas || row("The question was searched as one area", "")}</div>
    <div class="dcard"><h3>Settings</h3>
      ${row("Papers up to", longDate(run.asked))}
      ${row("Mode", capital(run.mode))}
      ${row("Depth", capital(run.effort))}
      ${row("Searches", (run.queries || []).length)}
    </div></div>`;
}

// -- where the run's papers sit in the topic tree ---------------------------------------------

const TOPIC_ROW = 30;
// a leaf name runs to two lines, and leaves hang below their parent where the width is
const LEAF_ROW = 42;
const TOPIC_GAP = 34;
const TOPIC_COL = 12;
const LEAF_INDENT = 30;
const TOPIC_W = [150, 220, 240, 250];
const TOPIC_MAX = [150, 300, 320, 400];
const topics = { open: null, picked: "root", shown: new Map(), links: new Map(), at: new Map(), width: 0, watch: null };

const roleOf = (p) => p.role || (p.retrieved ? "ungraded" : "connector");
const topicX = (d) => TOPIC_W.slice(0, d).reduce((a, w) => a + w + TOPIC_GAP, 0);

function topicData() {
  const root = { id: "root", name: "This run", depth: 0, children: [], papers: [], up: null };
  const byKey = { root };
  for (const p of papers) {
    if (!p.topic_id || p.topic_id.length !== 3) continue;
    root.papers.push(p);
    let up = root;
    for (let d = 0; d < 3; d++) {
      const code = p.topic_id.slice(0, d + 1).join(".");
      let node = byKey["t" + code];
      if (!node) {
        node = { id: "t" + code, code, name: p.topic[d] || `topic ${code}`, depth: d + 1, children: [], papers: [], up };
        byKey[node.id] = node;
        up.children.push(node);
      }
      node.papers.push(p);
      up = node;
    }
  }
  // each top level topic keeps one line color for its branch
  const sorted = [...root.children].sort((a, b) => b.papers.length - a.papers.length);
  sorted.forEach((g, i) => { g.color = lineColor(i + 1); });
  for (const node of Object.values(byKey)) {
    let g = node;
    while (g.depth > 1) g = g.up;
    node.color = node.depth ? g.color : "var(--primary)";
  }
  return { root, byKey };
}

function topicLayout(root, width) {
  const out = [];
  let y = 0;
  const pack = (run, d, x0, below) => {
    if (!run.length) return;
    const room = Math.max(TOPIC_W[d], width - x0 - 6);
    const per = Math.max(1, Math.floor((room + TOPIC_COL) / (TOPIC_W[d] + TOPIC_COL)));
    const w = Math.min(TOPIC_MAX[d], Math.floor((room - (per - 1) * TOPIC_COL) / per));
    const h = d === 3 ? LEAF_ROW : TOPIC_ROW;
    run.forEach((kid, i) => {
      const c = i % per;
      if (i && !c) y += h;
      Object.assign(kid, { x: x0 + c * (w + TOPIC_COL), y: y + h / 2, w, h, kids: [], head: !c, below });
      out.push(kid);
    });
    y += h;
  };
  const walk = (node) => {
    const kids = topics.open.has(node.id) ? [...node.children].sort((a, b) => b.papers.length - a.papers.length) : [];
    Object.assign(node, { x: topicX(node.depth), w: TOPIC_W[node.depth], h: TOPIC_ROW, kids, head: true, below: false });
    out.push(node);
    if (!kids.length || node.depth === 2) {
      node.y = y + TOPIC_ROW / 2;
      y += TOPIC_ROW;
      pack(kids, node.depth + 1, node.x + LEAF_INDENT, true);
      return;
    }
    let run = [];
    for (const kid of kids) {
      if (!topics.open.has(kid.id)) { run.push(kid); continue; }
      pack(run, node.depth + 1, topicX(node.depth + 1), false);
      run = [];
      walk(kid);
    }
    pack(run, node.depth + 1, topicX(node.depth + 1), false);
    node.y = (kids[0].y + kids[kids.length - 1].y) / 2;
  };
  walk(root);
  return { nodes: out, height: y };
}

function topicLink(a, b) {
  if (b.below) {
    const x = a.x + 10;
    const top = a.y + 10;
    const r = Math.min(8, Math.max(0, b.y - top));
    return `M${x},${top} L${x},${b.y - r} Q${x},${b.y} ${x + r},${b.y} L${b.x},${b.y}`;
  }
  const x1 = a.x + a.w;
  const mid = (x1 + b.x) / 2;
  return `M${x1},${a.y} C${mid},${a.y} ${mid},${b.y} ${b.x},${b.y}`;
}

function roleBar(list) {
  const count = {};
  for (const p of list) count[roleOf(p)] = (count[roleOf(p)] || 0) + 1;
  return ROLE_ORDER.filter((r) => count[r]).map((r) => `<i class="role-fill role-${r}" style="flex:${count[r]}"></i>`).join("");
}

function roleTally(list) {
  const count = {};
  for (const p of list) count[roleOf(p)] = (count[roleOf(p)] || 0) + 1;
  return ROLE_ORDER.filter((r) => count[r]).map((r) => `<span><i class="role-dot role-${r}"></i>${count[r]} ${r}</span>`).join("");
}

function topicsTab() {
  const host = document.getElementById("p-topics");
  const { root, byKey } = topicData();
  if (!root.papers.length) {
    host.innerHTML = '<p class="empty">This report was written before papers carried their place in the topic tree.</p>';
    return;
  }
  // the top level opens, and a parent unfolds when it is picked, so the tree starts one screen tall
  if (!topics.open) topics.open = new Set(Object.values(byKey).filter((n) => n.depth < 2).map((n) => n.id));
  if (!byKey[topics.picked]) topics.picked = "root";
  topics.root = root;
  topics.byKey = byKey;
  topics.shown = new Map();
  topics.links = new Map();
  topics.at = new Map();
  const leaves = Object.values(byKey).filter((n) => n.depth === 3).length;
  host.innerHTML = `<div class="tp-head">
      <p>Where the ${root.papers.length} papers of this run sit in the corpus's own topic tree, ${root.children.length} top level topics down to ${leaves} leaves.
        Each bar splits a topic's papers by the role the reader gave them. Click a topic to open it and list its papers, and its dot to fold it.</p>
      <div class="tp-legend">${roleTally(root.papers)}</div></div>
    <div class="tp-wrap"><div class="tp-tree" id="tpt"><svg class="tp-links" id="tpl"></svg></div></div>
    <div class="tp-list" id="tpp"></div>`;
  const tree = document.getElementById("tpt");
  if (topics.watch) topics.watch.disconnect();
  topics.width = 0;
  topics.watch = new ResizeObserver(() => { if (Math.abs(tree.clientWidth - topics.width) > 1) drawTopics(); });
  topics.watch.observe(tree);
  drawTopics();
  topicPapers();
}

function drawTopics() {
  const host = document.getElementById("tpt");
  const svg = document.getElementById("tpl");
  if (!host) return;
  topics.width = host.clientWidth;
  const { nodes, height } = topicLayout(topics.root, topics.width);
  host.style.height = `${height + 6}px`;
  svg.setAttribute("height", String(height + 6));
  const keep = new Set(nodes.map((node) => node.id));
  for (const node of nodes) {
    let el = topics.shown.get(node.id);
    const internal = node.children.length > 0;
    if (!el) {
      el = document.createElement("div");
      el.className = `tp-node d${node.depth}`;
      const from = topics.at.get(node.up ? node.up.id : "root") || { x: node.x, y: node.y };
      el.style.transform = `translate(${from.x}px, ${from.y - node.h / 2}px)`;
      el.style.opacity = "0";
      el.innerHTML = `<button class="tp-dot" aria-label="fold"></button><button class="tp-name"></button><span class="tp-n"></span><span class="tp-roles"></span>`;
      el.querySelector(".tp-dot").onclick = () => {
        if (!internal) return pickTopic(node.id);
        if (topics.open.has(node.id)) {
          const shut = (x) => { topics.open.delete(x.id); x.children.forEach(shut); };
          shut(node);
        } else topics.open.add(node.id);
        drawTopics();
      };
      el.querySelector(".tp-name").onclick = () => pickTopic(node.id);
      el.onmousemove = (e) => showTip(e, `<div class="cp-t">${esc(node.name)}</div>
        <div class="cp-m">${node.papers.length} of this run's papers${node.up ? `, ${Math.round((100 * node.papers.length) / node.up.papers.length)}% of ${esc(node.up.name)}` : ""}</div>
        <div class="tp-tally">${roleTally(node.papers)}</div>${node.code ? `<div class="cp-m tech">topic ${node.code}</div>` : ""}`);
      el.onmouseleave = hideTip;
      host.append(el);
      topics.shown.set(node.id, el);
    }
    const open = topics.open.has(node.id) && internal;
    el.style.setProperty("--c", node.color);
    el.style.width = `${node.w}px`;
    el.style.height = `${node.h}px`;
    el.classList.toggle("open", open);
    el.classList.toggle("leaf", !internal);
    el.classList.toggle("tall", node.h === LEAF_ROW);
    el.classList.toggle("picked", node.id === topics.picked);
    el.querySelector(".tp-dot").innerHTML = internal ? (open ? "&minus;" : "+") : "";
    el.querySelector(".tp-name").textContent = node.name;
    el.querySelector(".tp-n").textContent = node.papers.length;
    el.querySelector(".tp-roles").innerHTML = roleBar(node.papers);
    requestAnimationFrame(() => {
      el.style.transform = `translate(${node.x}px, ${node.y - node.h / 2}px)`;
      el.style.opacity = "1";
    });
  }
  for (const [id, el] of topics.shown) {
    if (keep.has(id)) continue;
    const node = topics.byKey[id];
    let up = node.up;
    while (up && !keep.has(up.id)) up = up.up;
    if (up) el.style.transform = `translate(${up.x}px, ${up.y - node.h / 2}px)`;
    el.style.opacity = "0";
    el.style.pointerEvents = "none";
    topics.shown.delete(id);
    setTimeout(() => el.remove(), 320);
  }
  const want = new Set();
  for (const node of nodes) {
    for (const kid of node.kids) {
      if (!kid.head) continue;
      want.add(kid.id);
      let path = topics.links.get(kid.id);
      if (!path) {
        path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const start = kid.below ? { x: node.x + 10, y: node.y + 10, below: true } : { x: node.x + node.w, y: node.y };
        path.style.d = `path("${topicLink(node, start)}")`;
        svg.append(path);
        topics.links.set(kid.id, path);
      }
      path.setAttribute("class", "tp-link");
      path.style.setProperty("--c", kid.color);
      const d = `path("${topicLink(node, kid)}")`;
      requestAnimationFrame(() => { path.style.d = d; });
    }
  }
  for (const [id, path] of topics.links) {
    if (want.has(id)) continue;
    path.style.opacity = "0";
    topics.links.delete(id);
    setTimeout(() => path.remove(), 320);
  }
  topics.at = new Map(nodes.map((node) => [node.id, { x: node.x, y: node.y }]));
}

function pickTopic(id) {
  topics.picked = id;
  const node = topics.byKey[id];
  if (node && node.children.length && !topics.open.has(id)) {
    topics.open.add(id);
    drawTopics();
  }
  for (const [key, el] of topics.shown) el.classList.toggle("picked", key === id);
  topicPapers();
}

function topicPapers() {
  const node = topics.byKey[topics.picked] || topics.root;
  const rank = (p) => ROLE_ORDER.indexOf(roleOf(p));
  const list = [...node.papers].sort((a, b) => rank(a) - rank(b) || String(b.date).localeCompare(String(a.date)));
  const path = [];
  for (let n = node; n && n.depth; n = n.up) path.unshift(n.name);
  document.getElementById("tpp").innerHTML = `<div class="tp-lh" style="--c:${node.color}"><i></i>
      <span>${esc(path.length ? path.join(" / ") : "Every paper in this run")}</span><span class="tech">${list.length} papers</span></div>
    <ul>${list.map((p) => `<li><i class="role-dot role-${roleOf(p)}" title="${roleOf(p)}"></i>
      <span class="tp-y">${esc(String(p.date || "").slice(0, 4))}</span>
      <button class="tp-t" onclick="openPaper('${p.arxiv_id}')">${esc(deTeX(p.title))}</button>
      ${p.cited ? '<span class="cited-b">CITED</span>' : ""}
      ${node.depth < 3 ? `<span class="tp-leaf">${esc(p.topic[2] || "")}</span>` : ""}</li>`).join("")}</ul>`;
}

// -- one run ---------------------------------------------------------------------------------

function tab(name, quiet) {
  if (!TABS.includes(name)) name = "report";
  if (!quiet && run) location.hash = `#/run/${encodeURIComponent(run.slug)}/${name}`;
  for (const p of document.querySelectorAll(".tab-panel")) p.classList.toggle("active", p.id === "p-" + name);
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("active", b.dataset.t === name);
  hideTip();
  // a hidden panel measures zero, so the chart is laid out once its own tab is showing
  if (name === "graph" && run) graphTab();
  if (name === "topics" && run) topicsTab();
  if (!quiet) window.scrollTo(0, 0);
}

async function reading(slug, wanted) {
  const view = document.getElementById("view");
  view.innerHTML = '<p class="empty">Loading&hellip;</p>';
  const answer = await fetch(`api/runs/${encodeURIComponent(slug)}`);
  if (!answer.ok) { view.innerHTML = `<p class="empty">There is no report called ${esc(slug)}.</p>`; return; }
  run = await answer.json();
  // papers.json overwrites run.json's id list, and an older run that has only ids gets none
  papers = (run.papers || []).filter((p) => typeof p === "object");
  byId = Object.fromEntries(papers.map((p) => [p.arxiv_id, p]));
  nodeById = Object.fromEntries(((run.graph || {}).nodes || []).map((n) => [n.arxiv_id, n]));
  lineNames = ((run.sections || {}).lineages || []).map((l) => l.name || "");
  refs = REF_DEFAULT();
  topics.picked = "root";
  topics.open = null;
  pickedLine = linesOf().length ? 1 : 0;
  focusedNode = null;
  document.title = "GraphIV, " + run.question;

  const files = [["report.md", "The report (Markdown)"], ["papers.json", "Every paper (JSON)"],
    ["graph.json", "The graph (JSON)"], ["run.json", "Run settings (JSON)"]]
    .map(([f, l]) => `<a class="mi" href="files/${encodeURIComponent(slug)}/${f}" target="_blank">${l}</a>`).join("");
  const nCited = (run.cited || []).length;
  const byline = [`Asked ${longDate(run.asked)}`, `${papers.length || (run.papers || []).length} papers, ${nCited} cited in the report`,
    `${capital(run.mode)}, ${run.effort} depth`].join(" · ");
  view.innerHTML = `
    <div class="runhead">
      <a class="back" href="#/">&larr; Library</a>
      <h1 class="q">${esc(run.question)}</h1>
      <div class="byline">${esc(byline)}</div>
      <div class="actionbar">
        <button class="ab-btn primary" id="topcited">Open the top paper</button>
        <details class="menu"><summary class="ab-btn">Download &#9662;</summary>
          <div class="menu-body">${files}</div></details>
      </div>
    </div>
    <div class="tabs">${[["report", "Report"], ["methods", "Methods"], ["references", "Papers"], ["graph", "Graph"], ["topics", "Topics"], ["details", "Details"]]
      .map(([t, l]) => `<button data-t="${t}" onclick="tab('${t}')">${l}</button>`).join("")}</div>
    ${TABS.map((t) => `<div class="tab-panel" id="p-${t}"></div>`).join("")}`;

  reportTab();
  methodsTab();
  referencesTab();
  detailsTab();
  const first = papers.find((p) => p.cited) || papers[0];
  document.getElementById("topcited").onclick = () => first && openPaper(first.arxiv_id);
  tab(wanted || "report", true);
  window.scrollTo(0, 0);
}

// -- routing ---------------------------------------------------------------------------------

function route() {
  closePanel();
  hideTip();
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

// the report runs long, so the way back up is always one press away
function backToTop() {
  const button = document.getElementById("totop");
  const mark = () => button.classList.toggle("on", window.scrollY > 600);
  window.addEventListener("scroll", mark, { passive: true });
  button.onclick = () => window.scrollTo({ top: 0, behavior: "smooth" });
  mark();
}

async function start() {
  theme();
  backToTop();
  window.addEventListener("hashchange", route);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closePanel(); hideTip(); } });
  let sized = 0;
  window.addEventListener("resize", () => {
    clearTimeout(sized);
    sized = setTimeout(() => {
      const on = document.getElementById("p-graph");
      if (on && on.classList.contains("active") && run) graphTab();
    }, 150);
  });
  try { runs = await (await fetch("api/runs")).json(); } catch (e) { runs = []; }
  route();
}

start();
