"use client";

import { useMemo, useState } from "react";
import type { Paper } from "../lib/types";

export function PaperList({
  papers,
  paperCount,
  onSelectPaper,
}: {
  papers: Paper[];
  paperCount: number;
  onSelectPaper: (paper: Paper) => void;
}) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const roles = useMemo(
    () => [...new Set(papers.map((paper) => paper.role).filter(Boolean))].sort(),
    [papers],
  );
  const filtered = useMemo(() => {
    const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return papers.filter((paper) => {
      if (role && paper.role !== role) return false;
      const text = `${paper.title} ${paper.authors} ${paper.arxiv_id}`.toLocaleLowerCase();
      return words.every((word) => text.includes(word));
    });
  }, [papers, query, role]);

  return (
    <div className="report-papers">
      <div className="report-view-heading">
        <div>
          <p className="report-kicker">The evidence</p>
          <h2>Papers behind the report</h2>
          <p>Inspect a paper to see its authors, abstract, and original source.</p>
        </div>
        <span className="report-small-count">{papers.length} records</span>
      </div>

      {paperCount > papers.length && (
        <p className="report-notice">
          This report references {paperCount} papers. {papers.length} paper records are available here.
        </p>
      )}

      {papers.length > 0 ? (
        <>
          <div className="report-paper-controls">
            <label className="report-search-field">
              <span className="report-sr-only">Search papers by title, author, or arXiv ID</span>
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <circle cx="8.5" cy="8.5" r="5.5" /><path d="m13 13 4 4" />
              </svg>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title, author, or arXiv ID"
              />
            </label>
            <label className="report-role-field">
              <span>Role</span>
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="">All roles</option>
                {roles.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
          </div>
          <div className="report-results-line" aria-live="polite" aria-atomic="true">
            <span>{filtered.length} of {papers.length} papers</span>
            {(query || role) && (
              <button type="button" onClick={() => { setQuery(""); setRole(""); }}>
                Clear filters
              </button>
            )}
          </div>

          {filtered.length ? (
            <ul className="report-paper-list">
              {filtered.map((paper, index) => (
                <li key={paper.arxiv_id}>
                  <button type="button" className="report-paper-row" onClick={() => onSelectPaper(paper)}>
                    <span className="report-paper-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <span className="report-paper-copy">
                      <span className="report-paper-title">{paper.title || "Untitled paper"}</span>
                      <span className="report-paper-authors">{paper.authors || "Authors not included"}</span>
                      <span className="report-paper-id">arXiv:{paper.arxiv_id}</span>
                    </span>
                    <span className="report-paper-meta">
                      <span>{paper.year || paper.date.slice(0, 4) || "Undated"}</span>
                      <span className="report-role" data-role={paper.role || "ungraded"}>
                        {paper.role || "ungraded"}
                      </span>
                    </span>
                    <span className="report-paper-arrow" aria-hidden="true">↗</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="report-empty">
              <h3>No papers match these filters</h3>
              <p>Try another title, author, or arXiv ID, or clear your filters.</p>
              <button type="button" className="report-text-button" onClick={() => { setQuery(""); setRole(""); }}>
                Clear filters <span aria-hidden="true">↗</span>
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="report-empty">
          <h3>No paper records were saved</h3>
          <p>The report may still contain links to its sources.</p>
        </div>
      )}
    </div>
  );
}
