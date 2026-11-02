import { createElement } from "react";

export function EvidenceNote({ note }: { note?: string }) {
  if (!note) return null;
  return createElement("aside", { className: "report-evidence-note", "aria-label": "Evidence availability" },
    createElement("strong", null, "Evidence availability"),
    createElement("p", null, note));
}
