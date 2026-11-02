import "server-only";

import { backendRequest } from "./backend.ts";
import { validSlug } from "./data.ts";
import { researchInput, researchStages, validJobId, type ResearchJob, type ResearchStage } from "./research.ts";

const MAX_REQUEST_BYTES = 24_576;
const response = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
const error = (message: string, status: number) => response({ error: message }, status);
const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};

function safeText(value: unknown, max = 500): string {
  if (typeof value !== "string") return "";
  const token = process.env.GRAPHIV_API_TOKEN?.trim();
  return (token ? value.replaceAll(token, "[redacted]") : value).slice(0, max);
}

function normalizeJob(value: unknown): ResearchJob | null {
  const raw = record(value);
  const input = researchInput({ question: raw.question, mode: raw.mode, effort: raw.effort });
  if (!input || typeof raw.id !== "string" || !validJobId(raw.id)) return null;
  if (!["queued", "running", "complete", "failed"].includes(String(raw.status))) return null;
  const result = record(raw.result);
  const slug = typeof result.slug === "string" && validSlug(result.slug) ? result.slug : "";
  if (raw.status === "complete" && !slug) return null;
  return {
    ...input,
    id: raw.id,
    status: raw.status as ResearchJob["status"],
    created_at: safeText(raw.created_at, 50),
    result: slug ? { slug, papers: typeof result.papers === "number" && Number.isFinite(result.papers) ? Math.max(0, Math.floor(result.papers)) : 0 } : null,
    error: safeText(raw.error, 1_000) || null,
    ...(researchStages.includes(raw.stage as ResearchStage) ? { stage: raw.stage as ResearchStage } : {}),
  };
}

async function upstreamResponse(upstream: Response): Promise<Response> {
  const raw = record(await upstream.json());
  if (!upstream.ok) {
    if (upstream.status === 401 || upstream.status === 403) return error("Research is unavailable. The server connection does not have access.", 503);
    if (upstream.status === 404) return error("This research job is no longer available. Check the library for a saved report.", 404);
    const reasons = Array.isArray(raw.reasons) ? raw.reasons.slice(0, 8).map((reason) => safeText(reason)).filter(Boolean) : [];
    return response({ error: safeText(raw.error) || "The research request could not be completed.", ...(reasons.length ? { reasons } : {}) },
      [400, 413, 422, 429, 503].includes(upstream.status) ? upstream.status : 502);
  }
  const job = normalizeJob(raw);
  return job ? response(job, upstream.status === 202 ? 202 : 200) : error("The research server returned an invalid job status. Please check again.", 502);
}

async function readInput(request: Request): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) return null;
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_REQUEST_BYTES) {
        await reader.cancel();
        throw new RangeError("Research request is too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

export async function submitResearch(request: Request): Promise<Response> {
  // The private backend credential must not turn a cross-site form into a write request.
  let sameOrigin = false;
  try {
    const origin = new URL(request.headers.get("origin") || "");
    // Next.js may reconstruct request.url with its internal localhost listener.
    // The browser's Host header still identifies the public site receiving the POST.
    sameOrigin = ["http:", "https:"].includes(origin.protocol) && origin.host === (request.headers.get("host") || new URL(request.url).host);
  } catch { /* Missing or malformed origins cannot submit research. */ }
  if (!sameOrigin) return error("Research requests must come from this site.", 403);
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") return error("Send the research question as JSON.", 415);
  let input;
  try { input = researchInput(await readInput(request)); }
  catch (caught) { return error(caught instanceof RangeError ? "The question is too large." : "Enter a valid research question.", caught instanceof RangeError ? 413 : 422); }
  if (!input) return error("Enter a question of 1–4000 characters and choose a research mode and depth.", 422);
  try {
    const upstream = await backendRequest("/api/research", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }, 10_000);
    if (upstream.status === 404) return error("This server supports saved reports only. Research submission is not available.", 503);
    return await upstreamResponse(upstream);
  } catch {
    return error("Submission could not be confirmed. Check the library before starting the same question again.", 503);
  }
}

export async function checkResearch(jobId: string): Promise<Response> {
  if (!validJobId(jobId)) return error("This research job is not available.", 404);
  try { return await upstreamResponse(await backendRequest(`/api/jobs/${jobId}`)); }
  catch { return error("Progress could not be checked. Your research may still be running. Please check again.", 503); }
}
