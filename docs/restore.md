# Restoring the prebuilt store

Running GraphIV without building anything.
`docs/preprocess.md` is the other path, which builds the same store from the metadata dump.

The serve path needs four things, and nothing outside `./data`.

## 1. The store, 18 GB dump into 89 GB

Download the dump: **link pending**, to be hosted on Hugging Face.
The current build is `graphiv-2026-09-26.dump`, written by `pg_dump -Fc --compress=zstd:3`.

```bash
nix develop                    # postgres17 with pgvector, plus the pg-* helpers
nix run .#pg-init              # the project-local cluster at ./data/pg, socket ./.pg, port 5433
nix run .#pg-start
pg_restore -h ./.pg -p 5433 -d arxivkg --no-owner --jobs 4 graphiv-<date>.dump
```

One database, `arxivkg`, holding `papers` (3,164,437), `citations` (182,559,513, of which
73,808,475 are resolved and labeled), `topic_tree` (3,128,573 placed papers) and
`topic_names` (4,368 named tree nodes).
A fresh cluster from `pg-init` trusts every connection over its own socket, so give the daemon a
role of its own and set `local all all peer` before anything but you can reach it.
`ARXIVKG_PG_DSN` overrides the DSN.

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

Any OpenAI-compatible host, named under `[endpoints]` in `config.toml`.

| key | role |
| --- | --- |
| `LLM_API` | the endpoint, default `http://localhost:11434/v1` |
| `LLM_NAME` | the one model every call goes to |

A 26B instruct model with 32k context is the reference point, and one model answers every call,
since the reader, the schema, the method table and the prose all fit it.
We serve through [llama-router](https://git.kuroma.dev/kkuroma/llama-router), which this code
treats as a plain OpenAI-compatible server.

## 4. The citation graph export

The dump carries the tables and not the graph the ranking walks, which is a separate 400 MB file
of flat arrays that the server loads once at start instead of hopping the 65 GB table. Build it
after the restore, since nothing serves without it:

```bash
uv run python scripts/citation_preprocess/stage2_export_graph.py
```

## Full text

The dump ships none, and none is needed up front.
The reader parses `<html>/<YYMM>/<id>.html` when it is there, and otherwise pulls it from ar5iv
or arxiv.org at one request every three seconds, writing it under `[serve] FETCH_PATH` so the
supplied store stays read only. The dashboard serves a paper inline out of
`<pdf>/<YYMM>/<id>v<n>.pdf` on the same terms. `[serve] FETCH = false` turns the network half off,
and a paper with no full text anywhere degrades to its abstract rather than failing.
To build the stores up front, run `stage1_download_pdf.py` and `stage2_download_html.py`.

## Run it

```bash
uv sync
uv run python scripts/serve.py                          # MCP over stdio
uv run python scripts/serve.py --http --role api        # the tools, 6767
uv run python scripts/serve.py --http --role frontend   # the dashboard, 6969
```

Both ports live in the `[serve]` block of `config.toml`, and `GRAPHIV_CONFIG` points at a config
somewhere else. On NixOS, `nixosModules.default` writes that file and runs both roles as units,
which `nix/README.md` covers.

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
librechat, and point it at `http://127.0.0.1:6767/mcp` with `type: streamable-http`.
The frontend role serves a run's own files under `/files/<slug>/<name>`, PDFs at `/pdf/<arxiv_id>`
and the Research Library dashboard at `/`, from a process carrying no tools at all.

Nine tools, and the caller drives them: `refine`, `identify_areas`, `retrieve`, `mine`,
`read_paper`, `write_report`, `what_cites`, `search_papers` and `find_runs`. `GRAPHIV_READONLY=1`
registers eight of them, holding back `write_report`, the only one that writes a file.

The effort a caller passes decides the cost. `quick` is retrieve and mine at about a minute,
`standard` adds the full-text read, the method table and the written sections and measured 158
seconds over two areas on one RTX 3090, and `deep` lifts every cap. Runs serialize on the one GPU,
so keep client tool timeouts generous: the librechat wiring uses 7,200,000 ms.

Figures use the repo `theme.json`
([shunka-shuutou](https://git.kuroma.dev/kkuroma/shunka-shuutou-theme)).
