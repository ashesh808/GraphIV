# API application

Python HTTP and MCP entrypoint for local development and Azure Container Apps.

```text
main.py            command-line configuration
server.py          MCP transport, HTTP routes, authentication, and health checks
dashboard.py       saved-report routes and retained legacy dashboard assets
orchestration.py   bounded research jobs over the existing retrieval/report tools
Dockerfile         runtime-only container image
```

Tool implementations live in [`src/mcp`](../../src/mcp/README.md). Corpus and report
persistence live in [`src/storage`](../../src/storage/), described in
[`docs/storage.md`](../../docs/storage.md). The application reads
[`configs/runtime.toml`](../../configs/runtime.toml), or the file named by `GRAPHIV_CONFIG`.
Explicit deployment environment values override the configuration defaults.

## Running locally

```sh
uv run graphiv-serve                                  # MCP over stdio
uv run graphiv-serve --http --role both --port 8000     # MCP, research jobs, and library
uv run graphiv-serve --http --role frontend            # saved reports only, port 6969
```

`--host` and `--port` override the selected HTTP role's configured bind address and port.
The `api` role exposes MCP and research jobs; `frontend` exposes saved reports and the
legacy dashboard; `both` exposes both sets. Use `both` when the Next.js app needs research
submission and saved-report reads from the same backend.

The HTTP process starts without opening the corpus in its request handlers. Background
preparation loads the configured research backend; missing corpus artifacts or endpoint
configuration keep research unready while health and saved-report routes remain available.

## HTTP interface

| Method and route | Purpose |
| --- | --- |
| `GET /health/live` | Process liveness; no corpus or model request |
| `GET /health/ready` | Research readiness and concise missing-configuration/preparation reasons |
| `POST /api/research` | Queue one question through retrieval, mining, grounding, and report writing |
| `GET /api/jobs/{id}` | Read a queued, running, complete, or failed research job |
| `GET /api/runs` | List saved reports from the configured report store |
| `GET /api/runs/{slug}` | Read a report and its papers, graph, and structured sections |
| `GET /files/{slug}/{name}` | Download one of the five allowed report files |
| `/mcp` | Streamable HTTP MCP endpoint |

The health routes exist for every HTTP role. Research/job/MCP tools require `api` or `both`;
report routes require `frontend` or `both`. The root page and legacy static assets accompany
the report routes. PDF reads use the configured local cache and existing arXiv-fetch policy.

Research submissions accept only these public inputs:

```json
{
  "question": "What does citation-aware retrieval add to literature search?",
  "mode": "survey",
  "effort": "standard"
}
```

`question` must contain 1–4000 nonblank characters. Modes are `survey`, `frontier`,
`consensus`, `ancestry`, and `evolution`; effort is `quick`, `standard`, or `deep`.
Ranking constants stay in the retrieval recipes.

An accepted submission returns HTTP 202 with its job ID and `status_url`. Poll that URL
for `complete` or `failed`; a completed result includes the report slug and report API URL.
The coordinator runs one research job at a time, allows at most four queued/running jobs,
and retains at most 128 status records. A full queue returns HTTP 429 with `Retry-After`;
unready research returns HTTP 503. `GRAPHIV_READONLY=1` disables report-writing work,
including HTTP research submission.

## Authentication

Set `GRAPHIV_API_TOKEN` through deployment secrets. When set, the bearer token protects
all application routes except the two health routes, including MCP and saved reports.
Azure mode, an explicit `GRAPHIV_REQUIRE_AUTH=1`, or a non-loopback bind requires a token;
a missing required token makes application requests unavailable rather than public.

The Next.js server uses its server-only `GRAPHIV_API_TOKEN` value to authenticate backend
requests. Do not expose the token through a `NEXT_PUBLIC_` variable. Model-service keys
use the separate `GRAPHIV_LLM_API_KEY` and `GRAPHIV_EMBED_API_KEY` settings.

## Azure deployment and persistence

Build from the repository root:

```sh
docker build -f apps/api/Dockerfile -t graphiv-api .
```

The container runs `both` on `0.0.0.0:8000` and installs runtime dependencies only.
Training and research-evaluation dependencies remain in their own groups. Configure the
storage account and managed identity, publish a compatible corpus manifest, and supply
explicit external LLM/embedding endpoints and model identifiers. The embedding model and
dimensions must match the snapshot.

`GRAPHIV_RUNTIME=azure` selects deployment defaults; `GRAPHIV_STORAGE_BACKEND=azure`
uses downloaded immutable FAISS/SQLite/GraphExport artifacts and durable Blob reports.
The local cache is disposable. Report publication uploads content generations before the
final commit marker, so failed replacement uploads preserve the previously saved report.
Enable the Terraform `allow_report_reads` option when serving the saved-report library.

Run one Python process in one replica. MCP rankings and job status are in memory; they do
not survive a process restart, while completed Blob reports do. The coordinator serializes
its jobs with MCP tool calls to protect that shared session state. See
[`docs/storage.md`](../../docs/storage.md) for the artifact contract, environment variables,
cache behavior, and storage verification, and [`infra/azure`](../../infra/azure/README.md)
for deployment definitions.
