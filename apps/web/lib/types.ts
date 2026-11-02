export type DataSource = "live" | "example";
export type ConnectionStatus = "connected" | "example" | "error";

export interface RunSummary {
  slug: string;
  question: string;
  asked: string;
  mode: string;
  effort: string;
  papers: number;
  summary?: string;
}

export interface Paper {
  arxiv_id: string;
  title: string;
  authors: string;
  abstract: string;
  date: string;
  year: string;
  category: string;
  role: string;
  cited: boolean;
  retrieved: boolean;
  relevance: number | null;
  cosine: number | null;
  topic: string[];
}

export interface GraphNode {
  arxiv_id: string;
  title: string;
  date: string;
  role: string;
  cited_by: number;
  lines: number[];
  retrieved: boolean;
  cosine: number | null;
  magnet: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  intent: string;
  intentScore?: number;
  sentence: string;
  walked: boolean;
}

export interface ReportArea {
  question: string;
  seed: string;
  papers: string[];
  unanswered: string[];
}

export interface ReportSuccessor {
  arxiv_id: string;
  date: string;
  title: string;
  reach: number | null;
  intents: string[];
}

export interface ReportSections {
  answer: string;
  opening: string;
  claims: { title: string; body: string }[];
  areas: ReportArea[];
  open_questions: string[];
  methods: {
    table: string;
    rows: { name: string; year: string; values: Record<string, string>; papers: string[] }[];
    columns: { name: string; kind: string; description: string; options: string[] }[];
  };
  lineages: {
    name: string;
    description: string;
    papers: { arxiv_id: string; date: string; title: string }[];
  }[];
  successors?: ReportSuccessor[];
}

export interface RunDetail extends Omit<RunSummary, "papers"> {
  papers: Paper[];
  paperCount: number;
  sections: ReportSections;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  report: string;
  cited: string[];
  counts: Record<string, number>;
  seconds: Record<string, number>;
  evidenceNote?: string;
  degradedFeatures?: string[];
}

export interface LibraryResult {
  runs: RunSummary[];
  source: DataSource;
  status: ConnectionStatus;
  message?: string;
}

export interface RunResult {
  run: RunDetail | null;
  source: DataSource;
  status: ConnectionStatus | "not-found";
  message?: string;
}
