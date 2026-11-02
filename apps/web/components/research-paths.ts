import { createElement, Fragment, type ReactNode } from "react";
import { arxivUrl, normalizePaperId } from "../lib/format.ts";
import type { Paper, ReportSections, ReportSuccessor } from "../lib/types";

interface Props {
  lineages: ReportSections["lineages"];
  successors?: ReportSuccessor[];
  papers: Paper[];
  onSelectId: (id: string) => void;
  renderMarkdown?: (text: string) => ReactNode;
}

export function ResearchPaths({ lineages, successors = [], papers, onSelectId, renderMarkdown }: Props) {
  if (!lineages.length && !successors.length) return null;
  const known = new Set(papers.map((paper) => normalizePaperId(paper.arxiv_id)));
  function paperLink(paper: { arxiv_id: string; date: string; title: string }) {
    const title = paper.title || paper.arxiv_id;
    const validDate = /^\d{4}-\d{2}-\d{2}$/.test(paper.date) && Number.isFinite(Date.parse(paper.date));
    const link = known.has(normalizePaperId(paper.arxiv_id))
      ? createElement("button", { type: "button", onClick: () => onSelectId(paper.arxiv_id), "aria-label": `Inspect ${title}` }, title)
      : createElement("a", { href: arxivUrl(paper.arxiv_id), target: "_blank", rel: "noopener noreferrer", "aria-label": `Read ${title} on arXiv` }, title);
    return createElement("div", { className: "report-path-paper" },
      createElement("time", { dateTime: validDate ? paper.date : undefined }, validDate ? paper.date : "Date unavailable"), link);
  }
  return createElement(Fragment, null,
    lineages.length > 0 && createElement("section", { id: "report-lineages", className: "report-prose-section" },
      createElement("p", { className: "report-kicker" }, "How it got here"),
      createElement("h2", null, "Research lineages"),
      ...lineages.map((lineage, index) => createElement("div", { className: "report-lineage", key: index },
        createElement("h3", null, lineage.name || `Lineage ${index + 1}`),
        lineage.description && (renderMarkdown ? renderMarkdown(lineage.description) : createElement("p", { className: "report-path-description" }, lineage.description)),
        lineage.papers.length > 0 && createElement("ol", { className: "report-path-list" },
          ...lineage.papers.map((paper, index) => createElement("li", { key: `${paper.arxiv_id}-${index}` }, paperLink(paper))))))),
    successors.length > 0 && createElement("section", { id: "report-successors", className: "report-prose-section" },
      createElement("p", { className: "report-kicker" }, "What appeared next"),
      createElement("h2", null, "Follow-up papers"),
      createElement("p", { className: "report-path-description" }, "Precomputed citation-intent labels are predictions, not quotations."),
      createElement("ul", { className: "report-path-list report-successor-list" },
        ...successors.map((paper, index) => createElement("li", { key: `${paper.arxiv_id}-${index}` },
          paperLink(paper),
          (paper.intents.length > 0 || paper.reach !== null) && createElement("p", { className: "report-path-detail" },
            [paper.intents.length ? `Predicted intents: ${paper.intents.map((intent) => intent.replaceAll("_", " ")).join(", ")}` : "",
              paper.reach !== null ? `Cites ${paper.reach} ${paper.reach === 1 ? "paper" : "papers"} in this review` : ""].filter(Boolean).join(" · ")))))));
}
