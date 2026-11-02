import "server-only";

import { backendRequest as request, BackendConnectionError } from "./backend.ts";
import { exampleReports, exampleSummaries } from "./demo.ts";
import type {
  GraphEdge,
  GraphNode,
  LibraryResult,
  Paper,
  ReportSections,
  RunDetail,
  RunResult,
  RunSummary,
} from "./types";

const EXAMPLE_MESSAGE = "Showing example reports. Connect a research library to see your saved runs.";
const ERROR_MESSAGE = "The research library is unavailable. Please try again.";

const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const text = (value: unknown, fallback = ""): string =>
  typeof value === "string" ? value : fallback;
const array = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const strings = (value: unknown): string[] => array(value).filter((v): v is string => typeof v === "string");
const number = (value: unknown, fallback = 0): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;
const nullableNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const numericRecord = (value: unknown): Record<string, number> =>
  Object.fromEntries(Object.entries(record(value)).filter((entry): entry is [string, number] =>
    typeof entry[1] === "number" && Number.isFinite(entry[1])));

/** Run IDs are directory names, never URLs or paths. */
export function validSlug(value: string): boolean {
  return /^[\p{L}\p{N}][\p{L}\p{N}._ -]{0,199}$/u.test(value) && value !== "." && value !== "..";
}

export function normalizeSummary(value: unknown): RunSummary | null {
  const raw = record(value);
  const slug = text(raw.slug);
  if (!validSlug(slug)) return null;
  return {
    slug,
    question: text(raw.question).trim() || slug,
    asked: text(raw.asked),
    mode: text(raw.mode),
    effort: text(raw.effort),
    papers: Math.max(0, Math.floor(number(raw.papers))),
    ...(typeof raw.summary === "string" ? { summary: raw.summary } : {}),
  };
}

function normalizePaper(value: unknown): Paper | null {
  const raw = record(value);
  const id = text(raw.arxiv_id);
  if (!id) return null;
  return {
    arxiv_id: id,
    title: text(raw.title, id),
    authors: Array.isArray(raw.authors) ? strings(raw.authors).join(", ") : text(raw.authors),
    abstract: text(raw.abstract),
    date: text(raw.date),
    year: text(raw.year, text(raw.date).slice(0, 4)),
    category: text(raw.category),
    role: text(raw.role) || (raw.retrieved === false ? "connector" : "ungraded"),
    cited: raw.cited === true,
    retrieved: raw.retrieved !== false,
    relevance: nullableNumber(raw.relevance),
    cosine: nullableNumber(raw.cosine),
    topic: strings(raw.topic),
  };
}

function normalizeSections(value: unknown): ReportSections {
  const raw = record(value);
  const methods = record(raw.methods);
  const areas = array(raw.areas).map((value) => {
    const area = record(value);
    return { question: text(area.question), seed: text(area.seed), papers: strings(area.papers), unanswered: strings(area.unanswered) };
  });
  return {
    answer: text(raw.answer),
    opening: text(raw.opening),
    claims: array(raw.claims).map((value) => {
      const claim = record(value);
      return { title: text(claim.title), body: text(claim.body) };
    }),
    areas,
    open_questions: strings(raw.open_questions).length
      ? strings(raw.open_questions)
      : areas.flatMap((area) => area.unanswered),
    methods: {
      table: text(methods.table),
      rows: array(methods.rows).map((value) => {
        const row = record(value);
        return {
          name: text(row.name), year: String(row.year ?? ""), papers: strings(row.papers),
          values: Object.fromEntries(Object.entries(record(row.values)).map(([key, value]) => [key, String(value ?? "")])),
        };
      }),
      columns: array(methods.columns).map((value) => {
        const column = record(value);
        return { name: text(column.name), kind: text(column.kind), description: text(column.description), options: strings(column.options) };
      }),
    },
    lineages: array(raw.lineages).map((value) => {
      const line = record(value);
      return {
        name: text(line.name), description: text(line.description),
        papers: array(line.papers).map((value) => {
          const paper = record(value);
          return { arxiv_id: text(paper.arxiv_id).trim(), date: text(paper.date), title: text(paper.title) };
        }).filter((paper) => paper.arxiv_id),
      };
    }).filter((line) => line.name || line.description || line.papers.length),
    successors: array(raw.successors).map((value) => {
      const successor = record(value);
      const reach = nullableNumber(successor.reach);
      return {
        arxiv_id: text(successor.arxiv_id).trim(), date: text(successor.date), title: text(successor.title),
        reach: reach !== null && Number.isInteger(reach) && reach >= 0 ? reach : null,
        intents: strings(successor.intents).map((intent) => intent.trim()).filter(Boolean),
      };
    }).filter((successor) => successor.arxiv_id),
  };
}

export function normalizeRun(value: unknown, slug: string): RunDetail | null {
  const raw = record(value);
  if (!Object.keys(raw).length || typeof raw.question !== "string") return null;
  const summary = normalizeSummary({ ...raw, slug, papers: array(raw.papers).length });
  if (!summary) return null;
  const papers = array(raw.papers).map(normalizePaper).filter((paper): paper is Paper => paper !== null);
  const graph = record(raw.graph);
  const nodes: GraphNode[] = array(graph.nodes).map((value) => {
    const node = record(value);
    return {
      arxiv_id: text(node.arxiv_id), title: text(node.title, text(node.arxiv_id)), date: text(node.date),
      role: text(node.role, "ungraded"), cited_by: number(node.cited_by),
      lines: array(node.lines).filter((line): line is number => typeof line === "number" && Number.isFinite(line)),
      retrieved: node.retrieved !== false, cosine: nullableNumber(node.cosine), magnet: nullableNumber(node.magnet),
    };
  }).filter((node) => node.arxiv_id);
  const ids = new Set(nodes.map((node) => node.arxiv_id));
  const edges: GraphEdge[] = array(graph.edges).map((value) => {
    const edge = record(value);
    const intentScore = nullableNumber(edge.intent_score);
    return {
      source: text(edge.source), target: text(edge.target), intent: text(edge.intent),
      ...(intentScore !== null && intentScore >= 0 && intentScore <= 1 ? { intentScore } : {}),
      sentence: text(edge.sentence), walked: edge.walked === true,
    };
  }).filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  const rawSections = record(raw.sections);
  const degradedFeatures = strings(raw.degraded_features ?? rawSections.degraded_features);
  const availability = record(raw.evidence_availability ?? rawSections.evidence_availability);
  const evidenceNote = text(raw.evidence_note).trim() || text(rawSections.evidence_note).trim() ||
    (availability.citation_sentences === false
      ? "Citation sentences were unavailable for this report. Citation quotations and sentence-based dispute analysis are omitted."
      : "");
  return {
    ...summary, papers, paperCount: papers.length || array(raw.papers).length,
    sections: normalizeSections(raw.sections), graph: { nodes, edges },
    report: text(raw.report), cited: strings(raw.cited), counts: numericRecord(raw.counts), seconds: numericRecord(raw.seconds),
    ...(evidenceNote ? { evidenceNote } : {}),
    ...(degradedFeatures.length ? { degradedFeatures } : {}),
  };
}

function allowExamples(error: unknown): boolean {
  return !process.env.GRAPHIV_API_URL?.trim() && !process.env.GRAPHIV_API_TOKEN?.trim() && error instanceof BackendConnectionError;
}

export async function loadLibrary(): Promise<LibraryResult> {
  try {
    const response = await request("/api/runs");
    if (!response.ok) throw new Error("Library request failed");
    const raw: unknown = await response.json();
    if (!Array.isArray(raw)) throw new Error("Invalid library response");
    const runs = raw.map(normalizeSummary);
    if (runs.some((run) => run === null)) throw new Error("Invalid library row");
    return { runs: runs as RunSummary[], source: "live", status: "connected" };
  } catch (error) {
    if (allowExamples(error)) {
      return { runs: exampleSummaries, source: "example", status: "example", message: EXAMPLE_MESSAGE };
    }
    return { runs: [], source: "live", status: "error", message: ERROR_MESSAGE };
  }
}

export async function loadRun(slug: string): Promise<RunResult> {
  if (!validSlug(slug)) return { run: null, source: "live", status: "not-found" };
  try {
    const response = await request(`/api/runs/${encodeURIComponent(slug)}`);
    if (response.status === 404) return { run: null, source: "live", status: "not-found" };
    if (!response.ok) throw new Error("Report request failed");
    const raw: unknown = await response.json();
    const run = normalizeRun(raw, slug);
    if (!run) throw new Error("Invalid report response");
    return { run, source: "live", status: "connected" };
  } catch (error) {
    if (allowExamples(error)) {
      const run = exampleReports.find((run) => run.slug === slug) ?? null;
      return { run, source: "example", status: run ? "example" : "not-found", ...(run ? { message: EXAMPLE_MESSAGE } : {}) };
    }
    return { run: null, source: "live", status: "error", message: ERROR_MESSAGE };
  }
}
