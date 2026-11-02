"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import type { Paper, RunDetail } from "../lib/types";
import { CitationGraph } from "./citation-graph";
import { arxivUrl, Markdown, normalizePaperId } from "./markdown";
import { PaperList } from "./paper-list";
import { EvidenceNote } from "./evidence-note";
import { ResearchPaths } from "./research-paths";

type View = "report" | "papers" | "graph";
const VIEWS: View[] = ["report", "papers", "graph"];

function dateLabel(value: string): string {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("en", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date)
    : "Date not recorded";
}

function markdownDocument(run: RunDetail, source: "live" | "example"): string {
  if (run.report.trim()) return run.evidenceNote && !run.report.includes(run.evidenceNote)
    ? `${run.report}\n\n## Evidence availability\n\n${run.evidenceNote}\n` : run.report;
  const { sections } = run;
  const questions = [...new Set([...sections.open_questions, ...sections.areas.flatMap((area) => area.unanswered)].filter(Boolean))];
  const cell = (value: string) => value.replaceAll("|", "\\|").replaceAll("\n", " ");
  const columns = sections.methods.columns;
  const methodTable = sections.methods.table || (sections.methods.rows.length ? [
    `| Method | ${columns.map((column) => cell(column.name)).join(" | ")}${columns.length ? " |" : ""}`,
    `| --- | ${columns.map(() => "---").join(" | ")}${columns.length ? " |" : ""}`,
    ...sections.methods.rows.map((row) => `| ${cell(row.name)} | ${columns.map((column) => cell(row.values[column.name] || "Not reported")).join(" | ")}${columns.length ? " |" : ""}`),
  ].join("\n") : "");
  const content = [
    `# ${run.question}`,
    source === "example" ? "> Example report. This is illustrative content, not a completed research run." : "",
    `${dateLabel(run.asked)} · ${run.mode || "Mode not recorded"} · ${run.effort || "Effort not recorded"}`,
    run.evidenceNote ? `## Evidence availability\n\n${run.evidenceNote}` : "",
    sections.answer,
    sections.opening,
    ...sections.claims.map((claim) => `## ${claim.title}\n\n${claim.body}`),
    methodTable ? `## Methods\n\n${methodTable}` : "",
    ...sections.areas.map((area) => `## ${area.question || "Research area"}\n\n${area.papers.map((id) => `- [${id}](${arxivUrl(id)})`).join("\n")}`),
    ...sections.lineages.map((lineage) => `## ${lineage.name || "Research thread"}\n\n${lineage.description}\n\n${lineage.papers.map((paper) => `- [${paper.title || paper.arxiv_id}](${arxivUrl(paper.arxiv_id)})`).join("\n")}`),
    sections.successors?.length ? `## Follow-up papers\n\nPrecomputed citation-intent labels are predictions, not quotations.\n\n${sections.successors.map((paper) => `- ${paper.date} [${paper.title || paper.arxiv_id}](${arxivUrl(paper.arxiv_id)})${paper.intents.length ? ` (${paper.intents.join(", ")})` : ""}`).join("\n")}` : "",
    questions.length ? `## Open questions\n\n${questions.map((question) => `- ${question}`).join("\n")}` : "",
    run.papers.length ? `## Papers\n\n${run.papers.map((paper) => `- [${paper.title || paper.arxiv_id}](${arxivUrl(paper.arxiv_id)})`).join("\n")}` : "",
  ];
  return `${content.filter(Boolean).join("\n\n")}\n`;
}

function TabIcon({ view }: { view: View }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      {view === "report" ? <><path d="M5 2.5h7l3 3v12H5z" /><path d="M8 9h4M8 12h4M8 6h1" /></>
        : view === "papers" ? <><path d="M5 4h12M5 10h12M5 16h12" /><path d="M2 4h.1M2 10h.1M2 16h.1" strokeWidth="2" /></>
          : <><path d="m5 5 10 3-7 8-3-11Z" /><circle cx="5" cy="5" r="2" /><circle cx="15" cy="8" r="2" /><circle cx="8" cy="16" r="2" /></>}
    </svg>
  );
}

export function ReportWorkspace({ run, source }: { run: RunDetail; source: "live" | "example" }) {
  const [view, setView] = useState<View>("report");
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [graphSelection, setGraphSelection] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState("");
  const [backHref, setBackHref] = useState("/");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const dialog = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | SVGElement | null>(null);
  const paperHeadingId = useId();
  const sections = run.sections;
  const hasProse = Boolean(sections.answer || sections.opening || sections.claims.some((claim) => claim.body));
  const openQuestions = [...new Set([...sections.open_questions, ...sections.areas.flatMap((area) => area.unanswered)].filter(Boolean))];
  const hasMethods = Boolean(sections.methods.table || sections.methods.rows.length);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("graphiv.libraryLocation");
      if (!saved) return;
      const location = new URL(saved, window.location.origin);
      if (location.origin === window.location.origin && location.pathname === "/") {
        setBackHref(`${location.pathname}${location.search}`);
      }
    } catch {
      // The library remains reachable when browser storage is unavailable.
    }
  }, []);

  useEffect(() => {
    const panel = dialog.current;
    if (!selectedPaper || !panel) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (!panel.open) panel.showModal();
    closeButton.current?.focus({ preventScroll: true });
    return () => {
      document.body.style.overflow = overflow;
      if (panel.open) panel.close();
      if (opener.current?.isConnected) opener.current.focus({ preventScroll: true });
    };
  }, [selectedPaper]);

  function selectPaper(paper: Paper) {
    if (!dialog.current?.open) {
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement || active instanceof SVGElement ? active : null;
    }
    setSelectedPaper(paper);
  }

  function selectId(id: string) {
    const paper = run.papers.find((item) => normalizePaperId(item.arxiv_id) === normalizePaperId(id));
    if (paper) {
      selectPaper(paper);
      return;
    }
    const node = run.graph.nodes.find((item) => item.arxiv_id === id);
    selectPaper({
      arxiv_id: id,
      title: node?.title || id,
      date: node?.date || "",
      year: node?.date.slice(0, 4) || "",
      role: node?.role || "",
      authors: "",
      abstract: "",
      category: "",
      cited: false,
      retrieved: node?.retrieved ?? false,
      relevance: null,
      cosine: node?.cosine ?? null,
      topic: [],
    });
  }

  function changeTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % VIEWS.length;
    else if (event.key === "ArrowLeft") next = (index + VIEWS.length - 1) % VIEWS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = VIEWS.length - 1;
    else return;
    event.preventDefault();
    setView(VIEWS[next]);
    tabs.current[next]?.focus();
  }

  function showPapers() {
    setView("papers");
    tabs.current[1]?.focus();
  }

  function download() {
    const file = new Blob([markdownDocument(run, source)], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${run.slug.replace(/[^a-zA-Z0-9._-]/g, "-") || "graphiv-report"}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setExportStatus("Markdown file prepared for download.");
  }

  const markdown = (text: string) => <Markdown text={text} papers={run.papers} onSelectPaper={selectPaper} />;

  return (
    <main id="main-content" className="report-workspace">
      <div className="report-breadcrumb">
        <Link href={backHref} className="report-back"><span aria-hidden="true">←</span> Library</Link>
        <span className="report-breadcrumb-separator" aria-hidden="true">/</span>
        <span>Research report</span>
      </div>

      <header className="report-header">
        <div className="report-header-top">
          <p className="report-kicker">{source === "example" ? "Example research report" : "Saved research report"}</p>
          <button type="button" className="report-download" onClick={download}>
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 2v10m-4-4 4 4 4-4M4 13v4h12v-4" /></svg>
            Download <span className="report-download-format">.md</span>
          </button>
        </div>
        <h1>{run.question || "Untitled research report"}</h1>
        <div className="report-metadata">
          <span>{dateLabel(run.asked)}</span><span aria-hidden="true">·</span>
          <span className="report-mode">{run.mode || "Mode not recorded"}</span><span aria-hidden="true">·</span>
          <span>{run.effort ? `${run.effort} effort` : "Effort not recorded"}</span><span aria-hidden="true">·</span>
          <span>{run.paperCount} {run.paperCount === 1 ? "paper" : "papers"}</span>
        </div>
        <span role="status" className="report-sr-only">{exportStatus}</span>
      </header>

      {source === "example" && (
        <p className="report-example-note">
          <span className="report-example-dot" aria-hidden="true" />
          <strong>Example report.</strong> This preview uses illustrative content and connections.
        </p>
      )}

      <EvidenceNote note={run.evidenceNote} />

      <div className="report-tabs" role="tablist" aria-label="Research report views">
        {VIEWS.map((item, index) => (
          <button
            key={item}
            type="button"
            ref={(element) => { tabs.current[index] = element; }}
            id={`report-tab-${item}`}
            role="tab"
            aria-controls={`report-panel-${item}`}
            aria-selected={view === item}
            tabIndex={view === item ? 0 : -1}
            className={view === item ? "is-active" : ""}
            onClick={() => setView(item)}
            onKeyDown={(event) => changeTab(event, index)}
          >
            <TabIcon view={item} />
            {item === "report" ? "Report" : item === "papers" ? "Papers" : "Graph"}
            {item === "papers" && <span className="report-tab-count">{run.papers.length}</span>}
          </button>
        ))}
      </div>

      <section id="report-panel-report" role="tabpanel" aria-labelledby="report-tab-report" hidden={view !== "report"}>
        <div className="report-reading-layout">
          <nav className="report-contents" aria-label="Report contents">
            <span className="report-kicker">On this page</span>
            <a href="#report-overview">Overview</a>
            {sections.claims.some((claim) => claim.body) && <a href="#report-findings">Findings</a>}
            {hasMethods && <a href="#report-methods">Methods</a>}
            {sections.areas.length > 0 && <a href="#report-areas">Research areas</a>}
            {sections.lineages.length > 0 && <a href="#report-lineages">Research lineages</a>}
            {Boolean(sections.successors?.length) && <a href="#report-successors">Follow-up papers</a>}
            {openQuestions.length > 0 && <a href="#report-open-questions">Open questions</a>}
            <div className="report-contents-note">
              <span className="report-note-mark" aria-hidden="true">↗</span>
              Select an inline citation to inspect its source.
            </div>
          </nav>

          <article className="report-reading">
            <section id="report-overview" className="report-overview">
              <p className="report-kicker">01 / Overview</p>
              <h2>The short answer</h2>
              {sections.answer && <div className="report-answer">{markdown(sections.answer)}</div>}
              {sections.opening && markdown(sections.opening)}
              {!hasProse && run.report && markdown(run.report)}
              {!hasProse && !run.report && (
                <p className="report-notice">No report text was saved. You can still inspect the available papers and graph.</p>
              )}
            </section>

            {sections.claims.some((claim) => claim.body) && (
              <section id="report-findings" className="report-prose-section">
                <p className="report-kicker">02 / Findings</p>
                {sections.claims.filter((claim) => claim.body).map((claim, index) => (
                  <div className="report-finding" key={`${claim.title}-${index}`}>
                    <h2>{claim.title || `Finding ${index + 1}`}</h2>
                    {markdown(claim.body)}
                  </div>
                ))}
              </section>
            )}

            {hasMethods && (
              <section id="report-methods" className="report-prose-section">
                <p className="report-kicker">Comparison</p>
                <h2>Methods, side by side</h2>
                {sections.methods.table ? markdown(sections.methods.table) : (
                  <div className="report-table-scroll" role="region" tabIndex={0} aria-label="Methods comparison">
                    <table className="report-method-table">
                      <thead><tr><th scope="col">Method</th>{sections.methods.columns.map((column) => <th key={column.name} scope="col">{column.name}</th>)}</tr></thead>
                      <tbody>
                        {sections.methods.rows.map((row, index) => (
                          <tr key={`${row.name}-${index}`}>
                            <th scope="row">{row.name}{row.year && <small>{row.year}</small>}</th>
                            {sections.methods.columns.map((column) => <td key={column.name}>{row.values[column.name] || "Not reported"}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}

            {sections.areas.length > 0 && (
              <section id="report-areas" className="report-prose-section">
                <p className="report-kicker">Scope of the review</p>
                <h2>Research areas</h2>
                <div className="report-area-list">
                  {sections.areas.map((area, index) => (
                    <div key={`${area.question}-${index}`}>
                      <h3>{area.question || `Area ${index + 1}`}</h3>
                      <div className="report-paper-references">
                        {area.papers.slice(0, 8).map((id) => <button key={id} type="button" onClick={() => selectId(id)}>{id}<span aria-hidden="true">↗</span></button>)}
                        {area.papers.length > 8 && <button type="button" onClick={showPapers}>View all {area.papers.length} papers</button>}
                        {!area.papers.length && <span className="report-muted">No paper references included.</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <ResearchPaths lineages={sections.lineages} successors={sections.successors} papers={run.papers} onSelectId={selectId} renderMarkdown={markdown} />

            {openQuestions.length > 0 && (
              <section id="report-open-questions" className="report-prose-section">
                <p className="report-kicker">Still unresolved</p>
                <h2>Open questions</h2>
                <ul className="report-open-questions">{openQuestions.map((question, index) => <li key={index}>{markdown(question)}</li>)}</ul>
              </section>
            )}

            <footer className="report-reading-footer">
              <span className="report-kicker">Continue with the evidence</span>
              <button type="button" onClick={showPapers}>Explore {run.papers.length} papers <span aria-hidden="true">→</span></button>
            </footer>
          </article>
        </div>
      </section>

      <section id="report-panel-papers" role="tabpanel" aria-labelledby="report-tab-papers" hidden={view !== "papers"}>
        <PaperList papers={run.papers} paperCount={run.paperCount} onSelectPaper={selectPaper} />
      </section>

      <section id="report-panel-graph" role="tabpanel" aria-labelledby="report-tab-graph" hidden={view !== "graph"}>
        <CitationGraph
          nodes={run.graph.nodes}
          edges={run.graph.edges}
          selectedId={graphSelection}
          onSelectId={(id) => { setGraphSelection(id); selectId(id); }}
          onClearSelection={() => setGraphSelection(null)}
          example={source === "example"}
        />
      </section>

      <dialog
        ref={dialog}
        className="report-paper-dialog"
        aria-labelledby={paperHeadingId}
        onCancel={(event) => { event.preventDefault(); setSelectedPaper(null); }}
        onClick={(event) => {
          const panel = dialog.current;
          if (panel && event.target === panel && event.clientX < panel.getBoundingClientRect().left) setSelectedPaper(null);
        }}
      >
        {selectedPaper && (
          <div className="report-paper-detail">
            <div className="report-detail-top">
              <span className="report-kicker">{source === "example" ? "Example reading list · Paper details" : "Paper details"}</span>
              <button ref={closeButton} type="button" className="report-detail-close" onClick={() => setSelectedPaper(null)} aria-label="Close paper details">
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" /></svg>
              </button>
            </div>
            <div className="report-detail-meta">
              {selectedPaper.role && <span className="report-role" data-role={selectedPaper.role}>{selectedPaper.role}</span>}
              {selectedPaper.date && <span>{dateLabel(selectedPaper.date)}</span>}
            </div>
            <h2 id={paperHeadingId}>{selectedPaper.title || "Untitled paper"}</h2>
            <p className="report-detail-authors">{selectedPaper.authors || "Authors were not included in this report."}</p>
            <a className="report-original-link" href={arxivUrl(selectedPaper.arxiv_id)} target="_blank" rel="noopener noreferrer">
              Read on arXiv <span aria-hidden="true">↗</span>
            </a>
            <span className="report-detail-id">arXiv:{selectedPaper.arxiv_id}</span>
            <div className="report-detail-abstract">
              <h3>{source === "example" ? "Reading note" : "Abstract"}</h3>
              <p>{selectedPaper.abstract || "No abstract was included in this report. Open the original paper on arXiv for more detail."}</p>
            </div>
            {(selectedPaper.category || selectedPaper.topic.length > 0) && (
              <div className="report-detail-topics">
                {selectedPaper.category && <span>{selectedPaper.category}</span>}
                {selectedPaper.topic.map((topic) => <span key={topic}>{topic}</span>)}
              </div>
            )}
          </div>
        )}
      </dialog>
    </main>
  );
}
