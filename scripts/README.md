# scripts

The runnable entrypoints. Each is single purpose, imports from `graphiv`, and is never imported itself.

## Stages

```
seed.py           refresh the metadata JSONL from Kaggle
download_pdf.py   fetch missing PDFs
download_html.py  fetch missing LaTeXML HTML
citations.py      parse, label and classify the citation graph
consolidate.py    fold everything into the single Postgres store
topics.py         build the topic tree and its optional summaries
research.py       a question in, a grounded literature review out
serve.py          the MCP server and the dashboard
doomscroll.py     keyboard-driven human labeling, standalone
```

A full ingest runs them in the order listed.

## The flag grammar

Every stage except `doomscroll.py` shares one contract, in `graphiv.core.cli`.

```sh
uv run python scripts/<stage>.py --dry-run          # print the plan, change nothing
uv run python scripts/<stage>.py --include-<name>   # set <name> true
uv run python scripts/<stage>.py --set-<name> <v>   # set <name> to <v>
uv run python scripts/<stage>.py --config=<path>    # read another config.toml
```

Defaults come from that stage's `[stage.*]` table in `config.toml`, and a flag layers on top.
Every stage is idempotent, so re-running with the same config changes nothing.
