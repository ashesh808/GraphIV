export const researchModes = ["survey", "frontier", "consensus", "ancestry", "evolution"] as const;
export const researchEfforts = ["quick", "standard", "deep"] as const;

export type ResearchMode = typeof researchModes[number];
export type ResearchEffort = typeof researchEfforts[number];
export const researchStages = ["starting", "retrieving", "mining", "reading_papers", "composing_report", "publishing_report", "complete", "failed"] as const;
export type ResearchStage = typeof researchStages[number];

export interface ResearchInput {
  question: string;
  mode: ResearchMode;
  effort: ResearchEffort;
}

export interface ResearchJob extends ResearchInput {
  id: string;
  status: "queued" | "running" | "complete" | "failed";
  created_at: string;
  result: { slug: string; papers: number } | null;
  error: string | null;
  stage?: ResearchStage;
}

export function validJobId(value: string): boolean {
  return /^[a-f0-9]{32}$/.test(value);
}

export function researchInput(value: unknown): ResearchInput | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  if (Object.keys(raw).some((key) => !["question", "mode", "effort"].includes(key))) return null;
  if (typeof raw.question !== "string" || !raw.question.trim() || raw.question.length > 4_000) return null;
  if (!researchModes.includes(raw.mode as ResearchMode) || !researchEfforts.includes(raw.effort as ResearchEffort)) return null;
  return { question: raw.question.trim(), mode: raw.mode as ResearchMode, effort: raw.effort as ResearchEffort };
}

export function activeJob(job: ResearchJob): boolean {
  return job.status === "queued" || job.status === "running";
}
