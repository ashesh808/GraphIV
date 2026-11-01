"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Paper } from "../lib/types";

export function normalizePaperId(value: string): string {
  return value.replace(/v\d+$/i, "").toLowerCase();
}

export function arxivUrl(id: string): string {
  return `https://arxiv.org/abs/${id.split("/").map(encodeURIComponent).join("/")}`;
}

function paperFromLink(href: string, papers: Paper[]): Paper | undefined {
  try {
    const url = new URL(href, "https://graphiv.local");
    if (!/^(www\.)?arxiv\.org$/i.test(url.hostname)) return undefined;
    const id = decodeURIComponent(url.pathname.replace(/^\/(abs|pdf)\//, ""))
      .replace(/\.pdf$/i, "");
    return papers.find((paper) => normalizePaperId(paper.arxiv_id) === normalizePaperId(id));
  } catch {
    return undefined;
  }
}

export function Markdown({
  text,
  papers,
  onSelectPaper,
}: {
  text: string;
  papers: Paper[];
  onSelectPaper: (paper: Paper) => void;
}) {
  return (
    <div className="report-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => {
            const paper = href ? paperFromLink(href, papers) : undefined;
            return paper ? (
              <button
                type="button"
                className="report-citation"
                onClick={() => onSelectPaper(paper)}
                aria-label={`Inspect ${paper.title || paper.arxiv_id}`}
                title={paper.title || paper.arxiv_id}
              >
                {children}
              </button>
            ) : (
              <a href={href} target={href?.startsWith("#") ? undefined : "_blank"} rel="noreferrer noopener">
                {children}
              </a>
            );
          },
          table: ({ children }) => (
            <div className="report-table-scroll" tabIndex={0} role="region" aria-label="Report table">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
