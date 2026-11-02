"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import type { LibraryResult } from "@/lib/types";
import { ConnectionNote } from "./connection-note";
import { Icon } from "./icon";
import { ResearchForm } from "./research-form";

const modeNames: Record<string, string> = { survey: "Survey", frontier: "Frontier", consensus: "Consensus", ancestry: "Ancestry", evolution: "Evolution" };

function dateLabel(value: string) {
  const date = new Date(`${value.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(date.valueOf()) ? value || "Undated" : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

export function Library({ result }: { result: LibraryResult }) {
  const params = useSearchParams();
  const query = params.get("q") || "";
  const mode = params.get("mode") || "all";
  const sort = params.get("sort") || "newest";
  const search = useRef<HTMLInputElement>(null);
  const modes = Array.from(new Set(result.runs.map((run) => run.mode).filter(Boolean))).sort();

  useEffect(() => {
    try { sessionStorage.setItem("graphiv.libraryLocation", window.location.pathname + window.location.search); } catch { /* Browser back remains available without storage. */ }
  }, [params]);

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (!value || value === "all" || key === "sort" && value === "newest") next.delete(key);
    else next.set(key, value);
    const query = next.toString();
    window.history.replaceState(null, "", query ? `/?${query}` : "/");
  }

  function clearFilters() {
    window.history.replaceState(null, "", "/");
    search.current?.focus();
  }

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey && !target.closest("input,textarea,[contenteditable=true]")) {
        event.preventDefault();
        search.current?.focus();
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const shown = useMemo(() => {
    const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    return result.runs.filter((run) => (mode === "all" || run.mode === mode) && terms.every((term) => `${run.question} ${run.summary || ""} ${run.mode}`.toLocaleLowerCase().includes(term))).sort((a, b) => sort === "title" ? a.question.localeCompare(b.question) : sort === "oldest" ? a.asked.localeCompare(b.asked) : b.asked.localeCompare(a.asked));
  }, [result.runs, query, mode, sort]);

  return (
    <main id="main-content" className="library-page">
      <div className="library-heading">
        <div><h1>Research library<span className="title-period">.</span></h1><p>Reports and the papers behind them.</p></div>
        <span className="library-total"><Icon name="book" width="16" height="16" />{result.runs.length} {result.runs.length === 1 ? "report" : "reports"}</span>
      </div>

      <ConnectionNote status={result.status} message={result.message} />

      <ResearchForm />

      <div className="library-controls">
        <div className="library-search">
          <Icon name="search" width="18" height="18" />
          <label htmlFor="library-search" className="sr-only">Search research reports</label>
          <input ref={search} id="library-search" type="search" placeholder="Search questions or topics…" value={query} onChange={(event) => update("q", event.target.value)} aria-keyshortcuts="/" />
          <kbd aria-hidden="true">/</kbd>
        </div>
        <label className="select-control"><span className="sr-only">Filter by research mode</span><select value={mode} onChange={(event) => update("mode", event.target.value)}><option value="all">All modes</option>{modes.map((mode) => <option key={mode} value={mode}>{modeNames[mode] || mode}</option>)}</select><Icon name="chevron" width="16" height="16" /></label>
        <label className="select-control sort-control"><span className="sr-only">Sort reports</span><select value={sort} onChange={(event) => update("sort", event.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="title">Question A–Z</option></select><Icon name="chevron" width="16" height="16" /></label>
      </div>

      <div className="library-list-header" aria-hidden="true"><span>Research question</span><span>Mode</span><span>Created</span><span /></div>

      <div className="research-list" aria-label="Research reports">
        {shown.map((run, index) => <Link className="research-row" href={`/runs/${encodeURIComponent(run.slug)}`} key={run.slug}>
          <div className="research-question"><span className="row-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><div><h2>{run.question}</h2>{run.summary && <p className="row-summary">{run.summary}</p>}<div className="row-meta"><span>{run.papers} {run.papers === 1 ? "paper" : "papers"}</span><span className="meta-divider" aria-hidden="true" /><span>{run.effort ? `${run.effort[0].toUpperCase()}${run.effort.slice(1)} depth` : "Research report"}</span></div></div></div>
          <div className="row-mode"><span className={`mode-label mode-${run.mode}`}>{modeNames[run.mode] || run.mode || "Unspecified"}</span></div>
          <time className="row-date" dateTime={run.asked || undefined}>{dateLabel(run.asked)}</time>
          <span className="row-arrow"><Icon name="arrow" width="18" height="18" /></span>
        </Link>)}
        {!shown.length && <div className="library-empty"><Icon name={query || mode !== "all" ? "search" : "book"} width="28" height="28" /><h2>{result.status === "error" ? "The library is unavailable" : query || mode !== "all" ? "No matching reports" : "Your library starts here"}</h2><p>{result.status === "error" ? "Retry the connection above to load your reports." : query || mode !== "all" ? "Try another question or show all research modes." : "Reports saved by GraphIV will appear here, together with their papers and citations."}</p>{(query || mode !== "all") && <button className="button-secondary" onClick={clearFilters}>Clear filters</button>}</div>}
      </div>
      <footer className="library-footer"><span role="status" aria-live="polite">{shown.length} of {result.runs.length} reports{query ? ` matching “${query}”` : ""}</span><span className="library-footer-note">Original research settings preserved.<span className="footer-node" aria-hidden="true" /></span></footer>
    </main>
  );
}
