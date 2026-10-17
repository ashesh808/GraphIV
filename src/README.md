# src

The library everything else imports.
Nothing here runs on its own, and nothing here imports `scripts/`.

```
core/      the data types and clients every layer shares
retrieve/  BoundedField, which turns a question into a ranked pool with no language model
miner/     LeyLine, which reads a list of papers for what the field argues about
report/    the written review, with its method table and its citation check
eval/      the four benchmarks that score a recipe
mcp/       the tools an outside agent calls, one file per tool
webui/     the dashboard over past runs, in html and css
```

The layers stack as `mcp`, `report`, `miner`, `eval`, `retrieve`, `core`, top to bottom.
A layer may import the ones below it and never the ones above, and the import-linter contract in `pyproject.toml` checks that.

Every setting lives in a recipe file under `retrieval_recipes/`, one per mode.
Changing the score means editing a toml rather than code, and the `[miner]` block in the same file keeps each mode's scorer and miner matched.

## Where the Models Are

| Layer | Calls a model |
| --- | --- |
| `core`, `retrieve` | never |
| `miner` | once, in `reader.py`, to grade a list of papers |
| `report` | to design the method table, to fill it from full text, and to write |
| `mcp` | to refine a question and to split it into areas |

Everything else is arithmetic over the citation graph, so a ranking can be reproduced from the query vector alone.

The code from before the rewrite is in git at `d0ff854` and earlier, and `docs/decisions.md` records what was taken from it.
The preprocessing has no code here: its helper modules sit beside the scripts that use them.
