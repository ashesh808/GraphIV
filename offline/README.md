# Offline workflows

Jobs for preprocessing, training, index building, and exporting the dataset.
Each stage does one job; shared helpers stay beside the stages that use them.
The runtime API lives in [`apps/api/`](../apps/api/README.md), and evaluation and figure generation live in [`research/`](../research/README.md).

## Building the Store

The store is built by four task directories.
Every stage reads its queue off a `stage` column, does one thing and advances the rows that succeeded, so any stage can be stopped and rerun.

```
papers_preprocess/    the papers table, from the Kaggle snapshot to embeddings and review scores
topic_tree_creation/  the topic tree and its labels, from the embeddings
citation_preprocess/  the citations table, parsed from the html and labeled by intent
citation_labeler/     trains the intent labeler the citation stage loads
index_build/          the boundary for future index-building workflows
export/               dataset dumps, benchmark exports, and publication
manager/              local administration, scheduling, and its browser interface
```

Run `papers_preprocess` first.
The topic tree and the citations only read papers at stage 3 and write their own tables, so those two can run in either order, or at the same time.

`citation_labeler/` sits off the main path.
It writes no table, only the checkpoint that `citation_preprocess/stage1_label_citation.py` loads.

Each directory has its own README with its stages, and [`docs/preprocess.md`](../docs/preprocess.md) walks through the whole build in order.

## Flags

Plain argparse.
Every script reads `configs/offline.toml` from the repo root, or another file with `--config_path`.

```sh
uv run python offline/papers_preprocess/stage1_download_pdf.py --limit 1000
uv run python offline/citation_preprocess/stage0_create_citation.py --workers 16
```

## Benchmarks

[`research/recipe_tuning/`](../research/recipe_tuning/README.md) fits BoundedField's recipes on the published benchmarks and scores every recipe on them.
`configs/offline.toml` lists which recipes each one compares, and recipes that share a retrieval prefix share one pool, so six recipes cost one retrieval.

```sh
uv run python research/recipe_tuning/stage2_evaluate.py --split test
```

## Export

`export/` writes the full `pg_dump` that [`docs/restore.md`](../docs/restore.md) restores and the Parquet release we publish, both under `[export] EXPORT_PATH`.

```sh
uv run python offline/export/stage0_dump_store.py
uv run python offline/export/stage1_export_parquet.py
```

## The Manager

[`offline/manager/`](manager/README.md) keeps the store current, with its browser app in `offline/manager/webui/`.
It fetches the weekly snapshot and runs every stage above in order, one job at a time.

```sh
uv run python -m offline.manager
```

## The Server

```sh
uv run graphiv-serve                         # stdio
uv run graphiv-serve --http --role api        # the MCP tools
uv run graphiv-serve --http --role frontend   # the dashboard
```

The runtime entrypoint is in [`apps/api/`](../apps/api/README.md), with tool implementations in [`src/mcp/`](../src/mcp/README.md). `legacy/serve.py` forwards to the same entrypoint for existing callers.
The agent runs the research loop and decides what to search next.
