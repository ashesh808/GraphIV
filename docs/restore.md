# Restoring the prebuilt store (run GraphIV without building phases 1–5)

The serve path needs three things: the Postgres store, an embedding endpoint, and an LLM endpoint.
Nothing outside `./data` is required at query time.

## 1. The store (~23 GB dump → ~105 GB restored)

Download the dump: **link pending** (will be hosted on Hugging Face; current build
`graphiv-2026-07-03.dump`, `pg_dump -Fc` format — 8 tables incl. both embedding spaces and
per-paper author lists). Then:

```bash
nix develop                        # provides postgres17+pgvector and the pg-* helpers
nix run .#pg-init                  # init the project-local cluster at ./data/pg (socket ./.pg, port 5433)
nix run .#pg-start
pg_restore -h ./.pg -p 5433 -d arxivkg --no-owner --jobs 4 arxivkg-<date>.dump
```

The store is a single database `arxivkg`: `paper` (id ↔ arxiv_id), `citation` (177M edges with
intent/polarity), `paper_meta`, `paper_embedding` (768-d nomic, HNSW), `paper_topic`/`leaf`
(topic tree). Peer-auth over the project-local socket — no password. Anything (a rebuild, a
different location) can override the DSN with `ARXIVKG_PG_DSN`.

## 2. The embedding endpoint

Queries (and delta-ingest documents) are embedded by a llama.cpp server hosting the
[nomic-ai/nomic-embed-text-v2-moe GGUF](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe-GGUF)
(f16 recommended — verified cosine > 0.999 against the original SentenceTransformer). The server
must expose `/v1/embeddings` plus llama.cpp's `/tokenize`/`/detokenize` (used for exact
truncation), so it has to be llama-server, not an arbitrary OpenAI-compatible host:

```bash
llama-server --embedding -m nomic-embed-text-v2-moe.f16.gguf --alias nomic-embed-text-v2-moe \
  --port 11435 -ngl 99 -c 8192 -b 8192 -ub 2048 --parallel 4 --pooling mean
```

Point `embeddings.api` in `config.toml` (or `GRAPHIV_EMBED_API`) at it.

## 3. The LLM endpoint

GraphIV talks to **any OpenAI-compatible endpoint** — configure `llm` in
`config.toml`:

- `base_url` / `router` — the endpoint (default `http://localhost:11434`).
- `map_model` — schema/extract/judge calls; `narrator_model` — thinking-heavy compose/critique
  (a long-context variant of the same model works well); `vision_model` — the optional figure
  gallery (omit figures with effort ≤ 2 if you have no vision model).

Set these to whatever model names your server exposes; a ~27B instruct model with ≥32k context
is the reference point. We serve via [llama-router](https://git.kuroma.dev/kkuroma/llama-router)
(llama.cpp with load-on-demand model routing); its `/router/restart` recovery endpoint is used
opportunistically and failures are non-fatal on plain servers.

## 4. Full text (PDFs / HTML)

The dump ships **no full text** — none is needed up front. Per-paper extraction reads
`data/pdf/<YYMM>/` and `data/html/<YYMM>/` when present and otherwise **fetches on demand** from
arXiv/ar5iv (rate-limited ~1 req/3 s, written through to the same layout, cached forever; disable
with `--set-fetch false`). Missing full text degrades to abstract-only. To bulk-build these stores
instead, run phases 1–2.

## 5. Run

```bash
uv sync
uv run python scripts/research.py "your question" --set-effort 4
```

## 6. Serve as an MCP tool (optional)

`scripts/serve.py` exposes GraphIV to any MCP client (librechat, Claude Desktop, …)
over stdio (default) or loopback streamable-http (`--http`, port `$GRAPHIV_MCP_PORT`, default
8756 — for sandboxed clients that can't spawn a process in the repo). Tools:
`deep_research(question, effort, seed_arxiv_id, force_new)` (the endpoint; seeding retrieves
from a specific paper's title+abstract; when finished reports already cover a similar question
it returns `{"status":"similar_reports_exist", reports:[…]}` instead of running — the host asks
the user reuse-vs-fresh, `force_new` reruns), `refine_question` (corpus-probed candidate
questions on the local LLM — the host model only relays, so a small local host works),
`search_papers` / `paper_details` (grounded follow-ups, no GPU), `list_reports` /
`similar_reports` (past runs; the latter LLM-matches a question against past run questions),
`retrieve_research(research_ids)` (reload 1-3 past reports by research_id = report slug,
optionally `slug/config`; multiple ids come back banner-joined for side-by-side reading),
`list_report_papers` (a deep run's cohort: per-paper reader summaries + role/relevance grades
from `papers.json`), `ask_paper` (QA over one paper's full text) and
`ask_research(research_ids, question)` (QA over 1-3 finished reviews + cohorts — follow-ups
and cross-report synthesis without re-running), plus a `deep_research_flow`
prompt template packaging the refine → run → follow-up loop. The host chat model shares the GPU
with the pipeline: it gets evicted during a deep run and reloads on demand afterward
(Gemma-4-26B works well as the host — MoE, fast reload).

The http transport additionally serves run artifacts at `/files/<slug>/<cfg>/…` (figures,
`graph.png`, the interactive `graph.html`, `papers.json`, `report.pdf`) and a **run dashboard**
at `/` (all runs, per-stage timings, live progress) with per-run control centers at
`/run/<slug>/<cfg>` (report/papers/graph/judge/timings tabs + delete / purge-caches /
compile-pdf actions). Markdown returned over MCP rewrites relative asset links to
`$GRAPHIV_PUBLIC_URL` (default `http://127.0.0.1:<port>`) so images render in the client.

```json
{
  "mcpServers": {
    "graphiv": {
      "command": "uv",
      "args": ["run", "python", "scripts/serve.py"],
      "cwd": "/path/to/GraphIV"
    }
  }
}
```

Or, for a client that can't spawn stdio servers (e.g. a systemd-hardened librechat), run
`uv run python scripts/serve.py --http` and point the client at
`http://127.0.0.1:8756/mcp` with `type: streamable-http`. A NixOS reference deployment
(librechat + a `graphiv-mcp` unit wrapping this in the project dev shell) lives in the
author's nixos-configs (`parts/services/{librechat,graphiv}.nix`).

Calls are serialized (single GPU); each run is subprocess-isolated and returns the finished
`report.md`. A cold-cache effort-4 deep run measures ~9 minutes on one RTX 3090 — keep client
tool timeouts generous (the librechat wiring uses 7,200,000 ms).

Figures use the repo `theme.json`
([shunka-shuutou](https://git.kuroma.dev/kkuroma/shunka-shuutou-theme) Material palette).
