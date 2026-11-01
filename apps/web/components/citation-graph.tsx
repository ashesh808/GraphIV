"use client";

import { useId, useMemo, useState } from "react";
import type { GraphEdge, GraphNode } from "../lib/types";

const WIDTH = 1080;
const LEFT = 72;
const RIGHT = WIDTH - 72;

function dateValue(value: string): number | null {
  const date = Date.parse(value);
  return Number.isFinite(date) ? date : null;
}

function roleClass(role: string): string {
  if (role === "foundational") return "foundational";
  if (role === "core") return "core";
  if (role === "frontier") return "frontier";
  return "other";
}

function arrange(nodes: GraphNode[]) {
  const sorted = [...nodes].sort((a, b) => {
    const delta = (dateValue(a.date) ?? Infinity) - (dateValue(b.date) ?? Infinity);
    return (Number.isNaN(delta) ? 0 : delta) || a.arxiv_id.localeCompare(b.arxiv_id);
  });
  const dates = sorted.map((node) => dateValue(node.date)).filter((value): value is number => value !== null);
  const min = dates.length ? Math.min(...dates) : 0;
  const max = dates.length ? Math.max(...dates) : 1;
  const laneCount = Math.max(5, Math.ceil(Math.sqrt(nodes.length) * 1.2));
  const lanes: number[][] = Array.from({ length: laneCount }, () => []);
  const points = sorted.map((node, index) => {
    const date = dateValue(node.date);
    const ratio = date !== null && max > min ? (date - min) / (max - min) : (index + 1) / (sorted.length + 1);
    const x = LEFT + ratio * (RIGHT - LEFT);
    let lane = index % laneCount;
    let bestDistance = -1;
    for (let offset = 0; offset < laneCount; offset += 1) {
      const candidate = (index + offset) % laneCount;
      const distance = lanes[candidate].length ? Math.min(...lanes[candidate].map((held) => Math.abs(held - x))) : Infinity;
      if (distance > bestDistance) {
        bestDistance = distance;
        lane = candidate;
      }
    }
    lanes[lane].push(x);
    return { node, x, y: 58 + lane * 54 };
  });
  return { points, min, max, height: 112 + (laneCount - 1) * 54, hasDates: dates.length > 0 };
}

export function CitationGraph({
  nodes,
  edges,
  selectedId,
  onSelectId,
  onClearSelection,
  example = false,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelectId: (id: string) => void;
  onClearSelection: () => void;
  example?: boolean;
}) {
  const markerId = `citation-arrow-${useId().replace(/:/g, "")}`;
  const [limit, setLimit] = useState(15);
  const layout = useMemo(() => arrange(nodes), [nodes]);
  const pointById = useMemo(() => new Map(layout.points.map((point) => [point.node.arxiv_id, point])), [layout]);
  const plottedEdges = useMemo(
    () => edges.filter((edge) => pointById.has(edge.source) && pointById.has(edge.target)),
    [edges, pointById],
  );
  const axisTicks = useMemo(() => {
    const span = layout.max - layout.min;
    const shortRange = span < 366 * 24 * 60 * 60 * 1000;
    const yearSpan = new Date(layout.max).getUTCFullYear() - new Date(layout.min).getUTCFullYear();
    const count = shortRange
      ? Math.min(5, Math.floor(span / (24 * 60 * 60 * 1000)) + 1)
      : Math.min(5, yearSpan + 1);
    const monthDay = new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" });
    return Array.from({ length: Math.max(1, count) }, (_, index) => {
      const ratio = count <= 1 ? 0.5 : index / (count - 1);
      const date = new Date(layout.min + ratio * span);
      return { ratio, label: shortRange ? monthDay.format(date) : String(date.getUTCFullYear()) };
    });
  }, [layout.min, layout.max]);
  const related = selectedId ? edges.filter((edge) => edge.source === selectedId || edge.target === selectedId) : edges;
  const title = (id: string) => pointById.get(id)?.node.title || id;

  if (!nodes.length) {
    return (
      <div className="report-empty">
        <p className="report-kicker">Citation graph</p>
        <h2>No citation graph was saved</h2>
        <p>You can still read the report and inspect the available papers.</p>
      </div>
    );
  }

  return (
    <div className="report-graph">
      <div className="report-view-heading">
        <div>
          <p className="report-kicker">Connections in the literature</p>
          <h2>A view of the citation graph</h2>
          <p>{example ? "Illustrative connections demonstrate the graph; they are not extracted citation evidence." : "Select a paper to inspect it. Arrows point from a citing paper to the work it references."}</p>
        </div>
        <span className="report-small-count">{nodes.length} papers · {plottedEdges.length} connections</span>
      </div>
      <div className="report-graph-frame">
        <div className="report-graph-legend" aria-label="Paper roles">
          {[["foundational", "Foundational"], ["core", "Core"], ["frontier", "Frontier"], ["other", "Other roles"]].map(([role, label]) => (
            <span key={role}><i data-role={role} aria-hidden="true" />{label}</span>
          ))}
        </div>
        <div className="report-graph-scroll" tabIndex={0} role="region" aria-label="Scrollable citation map">
          <svg
            viewBox={`0 0 ${WIDTH} ${layout.height}`}
            className="report-graph-svg"
            role="group"
            aria-label={`Citation map with ${nodes.length} papers and ${plottedEdges.length} connections. Each paper is a button.`}
          >
            <defs>
              <marker id={markerId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 1 L 9 5 L 0 9" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </marker>
            </defs>
            {layout.hasDates && (
              <g className="report-graph-axis" aria-hidden="true">
                <line x1={LEFT} x2={RIGHT} y1={layout.height - 32} y2={layout.height - 32} />
                {axisTicks.map(({ ratio, label }, index) => {
                  const x = LEFT + ratio * (RIGHT - LEFT);
                  return (
                    <g key={index}>
                      <line x1={x} x2={x} y1={layout.height - 36} y2={layout.height - 28} />
                      <text x={x} y={layout.height - 10} textAnchor="middle">
                        {label}
                      </text>
                    </g>
                  );
                })}
              </g>
            )}
            <g aria-hidden="true">
              {plottedEdges.map((edge, index) => {
                const source = pointById.get(edge.source)!;
                const target = pointById.get(edge.target)!;
                const length = Math.hypot(target.x - source.x, target.y - source.y) || 1;
                const endX = target.x - ((target.x - source.x) / length) * 11;
                const endY = target.y - ((target.y - source.y) / length) * 11;
                const isRelated = edge.source === selectedId || edge.target === selectedId;
                return (
                  <line
                    key={`${edge.source}-${edge.target}-${index}`}
                    className={`report-graph-edge${isRelated ? " is-related" : ""}${selectedId && !isRelated ? " is-muted" : ""}`}
                    x1={source.x} y1={source.y} x2={endX} y2={endY}
                    markerEnd={`url(#${markerId})`}
                  />
                );
              })}
            </g>
            {layout.points.map(({ node, x, y }, index) => (
              <g
                key={node.arxiv_id}
                className={`report-graph-node${selectedId === node.arxiv_id ? " is-selected" : ""}`}
                data-role={roleClass(node.role)}
                transform={`translate(${x} ${y})`}
                role="button"
                tabIndex={0}
                aria-label={`Inspect ${node.title || node.arxiv_id}${node.date ? `, ${node.date.slice(0, 4)}` : ""}${node.role ? `, ${node.role}` : ""}`}
                aria-pressed={selectedId === node.arxiv_id}
                onClick={() => onSelectId(node.arxiv_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectId(node.arxiv_id);
                  }
                }}
              >
                <title>{node.title || node.arxiv_id}</title>
                <circle className="report-graph-node-hit" r="20" />
                <circle className="report-graph-node-ring" r="13" />
                <circle className="report-graph-node-dot" r={node.role === "foundational" ? 7 : 5.5} />
                {(index < 7 || selectedId === node.arxiv_id) && (
                  <text x="13" y="4" aria-hidden="true">{node.arxiv_id}</text>
                )}
              </g>
            ))}
          </svg>
        </div>
        <p className="report-graph-caption">
          {layout.hasDates ? "Horizontal position follows publication date. Vertical spacing is for readability." : "Publication dates were not included; positions are arranged for readability."}
          {edges.length !== plottedEdges.length && ` ${edges.length - plottedEdges.length} connections have missing node records and appear only in the list below.`}
        </p>
      </div>

      <section className="report-relations" aria-labelledby="report-relations-heading">
        <div className="report-relations-heading">
          <h3 id="report-relations-heading">{example ? "Example connections" : "Citation relationships"}</h3>
          {selectedId ? <button type="button" onClick={onClearSelection}>Show all connections</button> : <span>{related.length} recorded</span>}
        </div>
        {related.length ? (
          <>
            <ul>
              {related.slice(0, limit).map((edge, index) => (
                <li key={`${edge.source}-${edge.target}-${edge.intent}-${index}`}>
                  <div className="report-relation-pair">
                    <button type="button" onClick={() => onSelectId(edge.source)}>{title(edge.source)}</button>
                    <span className="report-relation-direction">cites <span aria-hidden="true">→</span></span>
                    <button type="button" onClick={() => onSelectId(edge.target)}>{title(edge.target)}</button>
                    {edge.intent && <span className="report-relation-intent">{edge.intent.replaceAll("_", " ")}</span>}
                  </div>
                  {edge.sentence && <p className="report-relation-sentence">“{edge.sentence}”</p>}
                </li>
              ))}
            </ul>
            {related.length > limit && (
              <button type="button" className="report-text-button" onClick={() => setLimit((value) => value + 20)}>
                Show more relationships <span aria-hidden="true">↓</span>
              </button>
            )}
          </>
        ) : <p className="report-muted">No citation relationships were saved{selectedId ? " for this paper" : " in this report"}.</p>}
      </section>
    </div>
  );
}
