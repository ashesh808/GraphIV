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

## Choosing how a question is answered

`--set-rank` picks the selector, and two of the five are the ones a person should see.

```sh
--set-rank joint        # survey: the lineage a field is built on, no reserved slots
--set-rank trajectory   # frontier: recent work, with slots reserved for it
```

Both spend eight slots on LeyLine, so the mode changes only the score and the reservation.
`joint` also raises the landmark budget, to 50/100/150/200 against 30/60/90/120.
`ppr`, `frontier` and `indegree` still resolve, and exist for the experiments.

Over MCP nobody passes this by hand: `refine_question` tags each candidate `survey` or
`frontier` and `deep_research` takes that mode. A batch run has nobody to ask, so this script
falls back to `[stage.research] rank`.
