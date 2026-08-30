# Restoring the prebuilt store

Running GraphIV without building anything.
`docs/preprocess.md` is the other path, which builds the same store from the metadata dump.

The serve path needs three things, and nothing outside `./data`.

## 1. The store, 18 GB dump into 87 GB

Download the dump: **link pending**, to be hosted on Hugging Face.
The current build is `graphiv-2026-08-30.dump`, written by `pg_dump -Fc --compress=zstd:3`.

```bash
nix develop                    # postgres17 with pgvector, plus the pg-* helpers
nix run .#pg-init              # the project-local cluster at ./data/pg, socket ./.pg, port 5433
nix run .#pg-start
pg_restore -h ./.pg -p 5433 -d arxivkg --no-owner --jobs 4 graphiv-<date>.dump
```

One database, `arxivkg`, holding `papers` (3,141,674), `citations` (180,690,765, of which
72,835,096 are resolved and labeled) and `topics` (4,368 named tree nodes).
Peer auth over the project-local socket, so no password, and `ARXIVKG_PG_DSN` overrides the DSN.

`pg_restore` rebuilds every index from scratch and the HNSW over 3.1M halfvec rows is most of
that time, so give it `maintenance_work_mem` and expect it to outlast the data load.

## 2. The embedding endpoint

Queries and delta documents are embedded by a llama.cpp server hosting the
[nomic-embed-text-v2-moe GGUF](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe-GGUF) at
f16, which is cosine > 0.999 against the original SentenceTransformer.

```bash
llama-server --embedding -m nomic-embed-text-v2-moe.f16.gguf --alias nomic-embed-text-v2-moe \
  --port 11435 -ngl 99 -c 8192 -b 8192 -ub 2048 --parallel 4 --pooling mean
```

It has to be llama-server rather than any OpenAI-compatible host, since documents are truncated
client-side through `/tokenize`. Point `embeddings.api` or `GRAPHIV_EMBED_API` at it.

## 3. The LLM endpoint

Any OpenAI-compatible host, configured under `llm` in `config.toml`.

| key | role |
| --- | --- |
| `base_url`, `router` | the endpoint, default `http://localhost:11434` |
| `map_model` | schema, extract and judge calls |
| `narrator_model` | compose and critique, so a long-context variant of the same model fits |
| `vision_model` | the figure gallery, optional below effort 3 |

A 27B instruct model with 32k context is the reference point.
We serve through [llama-router](https://git.kuroma.dev/kkuroma/llama-router), whose
`/router/restart` is called opportunistically and is non-fatal on a plain server.

## Full text

The dump ships none, and none is needed up front.
Extraction reads `data/pdf/<YYMM>/` and `data/html/<YYMM>/` when present and otherwise fetches
from arXiv or ar5iv at about one request every three seconds, writing through to the same layout.
Missing full text degrades to abstract only, and `--set-fetch false` disables the network half.
To bulk build the stores instead, run `stage1_download_pdf.py` and `stage2_download_html.py`.

## Run it

```bash
uv sync
uv run python scripts/research.py "your question" --set-effort 4

uv run python scripts/serve.py            # MCP over stdio
uv run python scripts/serve.py --http     # streamable-http, 127.0.0.1:$GRAPHIV_MCP_PORT, 8756
```

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

Use `--http` for a client that cannot spawn a process in the repo, such as a systemd-hardened
librechat, and point it at `http://127.0.0.1:8756/mcp` with `type: streamable-http`.
That transport also serves run artifacts under `/files/<slug>/<cfg>/`, PDFs at `/pdf/<arxiv_id>`
and the Research Library dashboard at `/`.

Deep runs serialize on the one GPU and each is subprocess isolated.
A cold-cache effort-4 run measures about 9 minutes on one RTX 3090, so keep client tool timeouts
generous. The librechat wiring uses 7,200,000 ms.

The tool list, the dashboard and the NixOS reference deployment get their own page in the next
docs pass. Figures use the repo `theme.json`
([shunka-shuutou](https://git.kuroma.dev/kkuroma/shunka-shuutou-theme)).
