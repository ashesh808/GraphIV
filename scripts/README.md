# scripts

The runnable entrypoints. Each is single purpose and is never imported by anything else.

## The build

Four task directories. Every stage reads its queue off a `stage` column, does one thing, and
advances the rows that succeeded, so any of them can be killed and re-run.

```
papers_preprocess/    Kaggle JSON -> the papers table, downloaded, embedded and reviewed
topic_tree_creation/  papers.embed_full -> the topic_tree and topic_names tables
citation_preprocess/  rendered HTML -> the citations table, labeled by intent
citation_labeler/     the teacher prompt and the student checkpoint the labeler loads
```

`papers_preprocess` runs first. Nothing after it depends on anything but `papers.stage`, so
`topic_tree_creation` and `citation_preprocess` both read papers at stage 3 and write only their
own tables, which makes their order between themselves free.

`citation_labeler/` is off the critical path. It writes no table and only leaves a checkpoint,
which `citation_preprocess/stage1_label_citation.py` picks up.

Each directory carries its own README with the stage list and the queue semantics, and
`docs/preprocess.md` is the whole build in order.

## Flags

Plain argparse, with `config.toml` read from the repo root or `--config_path`.

```sh
uv run python scripts/papers_preprocess/stage1_download_pdf.py --limit 1000
uv run python scripts/citation_preprocess/stage0_create_citation.py --workers 16
```

## The endpoint

`research.py` and `serve.py` are parked in `.legacy/scripts/` until `src/` is rebuilt against the
three-table store.
