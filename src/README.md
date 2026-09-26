# src

The importable library. Nothing here is an entrypoint and nothing here imports `scripts/`.

```
core/      the contracts, the citation graph as CSR, the embedding and router clients
retrieve/  a question and a date cap -> a ranked pool, no language model anywhere in it
miner/     a list of papers -> what the field argues with, and how it got there
report/    that -> the document, its method table, and the guard every draft passes through
eval/      the four benchmarks that score a recipe
mcp/       the tool surface an outside agent drives, one file per tool
webui/     the dashboard over past runs, which is html and css rather than python
```

The layer order is `mcp`, `report`, `miner`, `eval`, `retrieve`, `core`, enforced by the
import-linter contract in `pyproject.toml`. A recipe file under `retrieval_recipes/` names which
components a pipeline holds and what every exponent is, so changing the score edits a toml and no
code. The `[miner]` block of the same file carries everything the mining layer is tuned by, which
is how one mode gets a matched scorer and miner.

## Where the models are

| layer | calls a model |
| --- | --- |
| `core`, `retrieve` | never |
| `miner` | once, in `reader.py`, to grade a list of papers |
| `report` | to design the method table and to fill it from full text |
| `mcp` | to refine a question and to split it into areas |

Everything else is arithmetic over the citation graph, so a ranking is reproducible from the query
vector alone.

The pre-rewrite versions are parked in `.legacy/graphiv/`, which git does not track, and
`docs/decisions.md` records what was taken from it and what was left behind.

Preprocessing has no code here. `scripts/citation_labeler/` carries the two modules it imports as
siblings, the same way `citation_preprocess/` carries `citation_regex.py`.
