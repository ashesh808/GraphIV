import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";

import { checkResearch, submitResearch } from "../lib/research-server.ts";
import { activeJob, researchInput, validJobId } from "../lib/research.ts";

const id = "a".repeat(32);
const input = { question: "What are the limits of citation-based retrieval?", mode: "survey", effort: "standard" };
const queued = { ...input, id, status: "queued", created_at: "2026-11-01T12:00:00Z", result: null, error: null };

function isolate(t: TestContext) {
  const originalFetch = globalThis.fetch;
  const originalUrl = process.env.GRAPHIV_API_URL;
  const originalToken = process.env.GRAPHIV_API_TOKEN;
  process.env.GRAPHIV_API_URL = "https://research.example/base";
  process.env.GRAPHIV_API_TOKEN = "private-server-token";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalUrl === undefined) delete process.env.GRAPHIV_API_URL; else process.env.GRAPHIV_API_URL = originalUrl;
    if (originalToken === undefined) delete process.env.GRAPHIV_API_TOKEN; else process.env.GRAPHIV_API_TOKEN = originalToken;
  });
}

function request(body: unknown = input, origin = "https://graphiv.example") {
  return new Request("https://graphiv.example/api/research", {
    method: "POST", headers: { Origin: origin, "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

test("research validates a bounded question and supported controls", () => {
  assert.deepEqual(researchInput({ ...input, question: "  A question  " }), { ...input, question: "A question" });
  for (const value of [{ ...input, question: " " }, { ...input, question: "a".repeat(4001) }, { ...input, mode: "unknown" }, { ...input, effort: "unlimited" }, { ...input, url: "https://other.example" }]) assert.equal(researchInput(value), null);
  assert.equal(validJobId(id), true);
  for (const value of ["../runs", "https://other.example", "a".repeat(200)]) assert.equal(validJobId(value), false);
  assert.equal(activeJob({ ...queued, status: "running" } as Parameters<typeof activeJob>[0]), true);
});

test("submission uses a fixed backend path and keeps its credential server-side", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "https://research.example/base/api/research");
    assert.equal(options?.method, "POST");
    assert.equal(options?.cache, "no-store");
    assert.equal(options?.redirect, "error");
    assert.equal(new Headers(options?.headers).get("Authorization"), "Bearer private-server-token");
    assert.deepEqual(JSON.parse(String(options?.body)), input);
    return Response.json({ ...queued, status_url: "https://untrusted.example", private_field: "private-server-token" }, { status: 202 });
  };
  const response = await submitResearch(request());
  assert.equal(response.status, 202);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await response.json(), queued);
});

test("cross-site writes and unsupported fields never reach the backend", { concurrency: false }, async (t) => {
  isolate(t);
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return Response.json(queued); };
  assert.equal((await submitResearch(request(input, "https://other.example"))).status, 403);
  assert.equal((await submitResearch(request({ ...input, backend_url: "https://other.example" }))).status, 422);
  assert.equal(calls, 0);
});

test("the public Host is used when Next reconstructs an internal request URL", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => Response.json(queued, { status: 202 });
  const incoming = new Request("http://localhost:3010/api/research", {
    method: "POST", headers: { Host: "127.0.0.1:3010", Origin: "http://127.0.0.1:3010", "Content-Type": "application/json" }, body: JSON.stringify(input),
  });
  assert.equal((await submitResearch(incoming)).status, 202);
});

test("submission bounds streamed request bodies without relying on content length", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => { assert.fail("An oversized request must not reach the backend"); };
  assert.equal((await submitResearch(request({ ...input, question: "x".repeat(30_000) }))).status, 413);
});

test("readiness errors retain useful reasons and redact backend credentials", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => Response.json({ error: "Research runtime is not ready", reasons: ["Corpus snapshot is missing", "private-server-token"] }, { status: 503 });
  const response = await submitResearch(request());
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Research runtime is not ready", reasons: ["Corpus snapshot is missing", "[redacted]"] });
});

test("job polling keeps only safe report metadata and never follows a supplied URL", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async (url) => {
    assert.equal(url, `https://research.example/base/api/jobs/${id}`);
    return Response.json({ ...queued, status: "complete", result: { slug: "a-real-report", papers: 6, answer: "private-server-token", url: "https://other.example" } });
  };
  const response = await checkResearch(id);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(body.result, { slug: "a-real-report", papers: 6 });
  assert.equal(JSON.stringify(body).includes("private-server-token"), false);
});

test("invalid IDs and report paths cannot escape the fixed job routes", { concurrency: false }, async (t) => {
  isolate(t);
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return Response.json({ ...queued, status: "complete", result: { slug: "../other" } }); };
  assert.equal((await checkResearch("../../admin")).status, 404);
  assert.equal(calls, 0);
  assert.equal((await checkResearch(id)).status, 502);
});

test("polling preserves supported progress stages without trusting arbitrary fields", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => Response.json({ ...queued, status: "running", stage: "reading_papers", started_at: "2026-11-01T12:01:00Z" });
  assert.equal((await (await checkResearch(id)).json()).stage, "reading_papers");
  globalThis.fetch = async () => Response.json({ ...queued, stage: "arbitrary markup" });
  assert.equal((await (await checkResearch(id)).json()).stage, undefined);
});

test("lost jobs and unavailable connections have explicit recovery messages", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => Response.json({ error: "No such job" }, { status: 404 });
  let response = await checkResearch(id);
  assert.equal(response.status, 404);
  assert.match((await response.json()).error, /library/);
  globalThis.fetch = async () => { throw new Error("network unavailable"); };
  response = await checkResearch(id);
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /may still be running/);
  response = await submitResearch(request());
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /could not be confirmed/);
});

test("a read-only server and an expired credential do not masquerade as accepted jobs", { concurrency: false }, async (t) => {
  isolate(t);
  globalThis.fetch = async () => Response.json({ error: "Not Found" }, { status: 404 });
  let response = await submitResearch(request());
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /saved reports only/);
  globalThis.fetch = async () => Response.json({ error: "Unauthorized private-server-token" }, { status: 401 });
  response = await submitResearch(request());
  assert.equal(response.status, 503);
  assert.equal(JSON.stringify(await response.json()).includes("private-server-token"), false);
});
