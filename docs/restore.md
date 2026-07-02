# Restoring the prebuilt store (run GraphIV without building phases 1–5)

The serve path needs three things: the Postgres store, the embedding model, and an LLM endpoint.
Nothing outside `./data` + `./model` is required at query time.

## 1. The store (~17 GB dump → ~100 GB restored)

Download the dump: **link pending** (will be hosted on Hugging Face; the tracked filename is
`arxivkg-<date>.dump`, `pg_dump -Fc` format). Then:

```bash
nix develop                        # provides postgres17+pgvector and the pg-* helpers
nix run .#pg-init                  # init the project-local cluster at ./data/pg (socket ./.pg, port 5433)
nix run .#pg-start
pg_restore -h ./.pg -p 5433 -d arxivkg --no-owner --jobs 4 arxivkg-<date>.dump
```

The store is a single database `arxivkg`: `paper` (id ↔ arxiv_id), `citation` (173M edges with
intent/polarity), `paper_meta`, `paper_embedding` (768-d nomic, HNSW), `paper_topic`/`leaf`
(topic tree). Peer-auth over the project-local socket — no password. Anything (a rebuild, a
different location) can override the DSN with `ARXIVKG_PG_DSN`.

## 2. The embedding model

Queries are embedded locally with
[nomic-ai/nomic-embed-text-v2-moe](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe):

```bash
git clone https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe model/nomic-embed-text-v2-moe
```

## 3. The LLM endpoint

GraphIV talks to **any OpenAI-compatible endpoint** — configure `llm` in
`phases/global-config.json`:

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
uv run python phases/phase-6/run.py "your question" --set-effort 4
```

Figures use the repo `theme.json`
([shunka-shuutou](https://git.kuroma.dev/kkuroma/shunka-shuutou-theme) Material palette).
