import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";

import { loadLibrary, loadRun, normalizeRun, normalizeSummary, validSlug } from "../lib/data.ts";

function isolateApi(t: TestContext, url?: string): void {
  const previousFetch = globalThis.fetch;
  const previousUrl = process.env.GRAPHIV_API_URL;
  const previousToken = process.env.GRAPHIV_API_TOKEN;
  delete process.env.GRAPHIV_API_TOKEN;
  if (url === undefined) delete process.env.GRAPHIV_API_URL;
  else process.env.GRAPHIV_API_URL = url;
  t.after(() => {
    globalThis.fetch = previousFetch;
    if (previousUrl === undefined) delete process.env.GRAPHIV_API_URL;
    else process.env.GRAPHIV_API_URL = previousUrl;
    if (previousToken === undefined) delete process.env.GRAPHIV_API_TOKEN;
    else process.env.GRAPHIV_API_TOKEN = previousToken;
  });
}

test("backend credentials are sent only as a server request header", { concurrency: false }, async (t) => {
  isolateApi(t, "https://library.example");
  process.env.GRAPHIV_API_TOKEN = "server-only-test-token";
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "https://library.example/api/runs");
    assert.equal(new Headers(options?.headers).get("Authorization"), "Bearer server-only-test-token");
    return Response.json([]);
  };
  const result = await loadLibrary();
  assert.equal(result.status, "connected");
  assert.equal(JSON.stringify(result).includes("server-only-test-token"), false);
});

test("a configured backend token disables implicit example fallback", { concurrency: false }, async (t) => {
  isolateApi(t);
  process.env.GRAPHIV_API_TOKEN = "server-only-test-token";
  globalThis.fetch = unavailable;
  assert.equal((await loadLibrary()).status, "error");
});

function unavailable(): Promise<Response> {
  return Promise.reject(new TypeError("The server could not be reached"));
}

test("run IDs reject URL paths and accept generated directory names", () => {
  for (const slug of ["", ".", "..", "../x", "a/b", "%2fetc", "https://example.com", "a?b"])
    assert.equal(validSlug(slug), false, slug);
  assert.equal(validSlug("2026-10-28-example"), true);
  assert.equal(validSlug("A saved question"), true);
  assert.equal(normalizeSummary({ slug: "../bad" }), null);
});

test("an unreachable implicit local server offers explicitly labeled examples", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = unavailable;
  const result = await loadLibrary();
  assert.equal(result.source, "example");
  assert.equal(result.status, "example");
  assert.match(result.message ?? "", /example reports/i);
  assert.equal(result.runs.length, 4);
  assert.ok(result.runs.every((run) => run.papers > 0));
  assert.equal("graph" in result.runs[0], false);
  assert.equal("report" in result.runs[0], false);
});

test("example details resolve only known example IDs", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = unavailable;
  const library = await loadLibrary();
  const example = await loadRun(library.runs[0].slug);
  assert.equal(example.status, "example");
  assert.equal(example.source, "example");
  assert.ok(example.run?.papers.length);
  assert.equal(example.run?.paperCount, example.run?.papers.length);
  assert.deepEqual(example.run?.cited, []);
  assert.equal((await loadRun("not-an-example")).status, "not-found");
});

test("a connected empty library stays empty instead of showing examples", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = async () => Response.json([]);
  const result = await loadLibrary();
  assert.equal(result.source, "live");
  assert.equal(result.status, "connected");
  assert.deepEqual(result.runs, []);
});

test("a local HTTP error is surfaced rather than substituted with examples", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = async () => new Response("Unavailable", { status: 500 });
  const library = await loadLibrary();
  assert.equal(library.status, "error");
  assert.equal(library.source, "live");
  assert.deepEqual(library.runs, []);
  const report = await loadRun("example-retrieval-augmented-generation");
  assert.equal(report.status, "error");
  assert.equal(report.run, null);
});

test("a live report 404 never falls back to a matching example", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = async () => new Response("Missing", { status: 404 });
  const result = await loadRun("example-retrieval-augmented-generation");
  assert.equal(result.status, "not-found");
  assert.equal(result.source, "live");
  assert.equal(result.run, null);
});

test("configured API prefixes are retained and requests are uncached", { concurrency: false }, async (t) => {
  isolateApi(t, "https://library.example/base/");
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "https://library.example/base/api/runs");
    assert.equal(options?.cache, "no-store");
    assert.ok(options?.signal instanceof AbortSignal);
    return Response.json([
      { slug: "real-run", question: "A saved question", asked: "2026-01-01", mode: "survey", effort: "quick", papers: 3 },
    ]);
  };
  const result = await loadLibrary();
  assert.equal(result.source, "live");
  assert.equal(result.status, "connected");
  assert.equal(result.runs[0].slug, "real-run");
});

test("an explicitly configured unreachable server never offers examples", { concurrency: false }, async (t) => {
  isolateApi(t, "https://library.example");
  globalThis.fetch = unavailable;
  const library = await loadLibrary();
  assert.equal(library.status, "error");
  assert.equal(library.source, "live");
  assert.deepEqual(library.runs, []);
  const report = await loadRun("example-retrieval-augmented-generation");
  assert.equal(report.status, "error");
  assert.equal(report.run, null);
});

test("malformed success responses become errors without example fallback", { concurrency: false }, async (t) => {
  isolateApi(t);
  globalThis.fetch = async () => Response.json({ invalid: "payload" });
  assert.equal((await loadLibrary()).status, "error");
  assert.equal((await loadRun("saved-run")).status, "error");
  globalThis.fetch = async () => Response.json([{ slug: "../invalid" }]);
  assert.equal((await loadLibrary()).status, "error");
});

test("legacy reports retain ID-only paper counts without inventing paper metadata", () => {
  const report = normalizeRun({ question: "Legacy report", papers: ["1706.03762", "2004.07180"] }, "legacy");
  assert.ok(report);
  assert.equal(report.paperCount, 2);
  assert.deepEqual(report.papers, []);
  assert.deepEqual(report.sections.methods.rows, []);
  assert.equal(normalizeRun({ invalid: "metadata" }, "legacy"), null);
});

test("normalization preserves open questions and discards dangling graph edges", () => {
  const report = normalizeRun({
    question: "Saved report",
    papers: [{ arxiv_id: "paper-a", title: "Paper A", authors: ["A. Reader", "B. Researcher"] }],
    sections: { areas: [{ question: "Area", unanswered: ["What is still unknown?"] }] },
    graph: {
      nodes: [{ arxiv_id: "paper-a" }, { arxiv_id: "paper-b" }],
      edges: [{ source: "paper-a", target: "paper-b", intent: "uses" }, { source: "paper-a", target: "missing" }],
    },
  }, "saved-report");
  assert.ok(report);
  assert.deepEqual(report.sections.open_questions, ["What is still unknown?"]);
  assert.equal(report.papers[0].authors, "A. Reader, B. Researcher");
  assert.equal(report.graph.edges.length, 1);
  assert.equal(report.graph.edges[0].target, "paper-b");
});
