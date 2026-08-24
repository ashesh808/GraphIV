# preprocess

Metadata and files to labels and a citation graph, behind the `Preprocessor` class. Heavy modules are imported inside the method that needs them, so constructing one stays cheap.

## Modules

```
parse/                citation resolver ladder -> the citation table
label/                policy refinement, the labeling app, the corpus sample, the teacher
intent/               DistilBERT student, training and corpus-wide inference
consolidate.py        everything -> the single Postgres and pgvector store
embed_corpus.py       dual-space corpus embedding, delta-aware, asym first
topics.py             the density-aware topic tree
community_summary.py  optional per-leaf LLM labels
_common.py            config bridge for the build modules
```

Parse writes citation rows and intent inference fills the intent columns, so column
ownership is never crossed. `bert/relabel` is the exception by design: it writes a side
table rather than `citation.intent`, so a new student never destroys the labels already in
the graph, and promoting it is a separate decision.

## Running it

```sh
uv run python scripts/citations.py --set-stage parse --dry-run
uv run python scripts/citations.py --set-stage label --set-step gold
uv run python scripts/citations.py --set-stage label --set-step refine
uv run python scripts/citations.py --set-stage label --set-step teacher
uv run python scripts/citations.py --set-stage bert --set-step train
uv run python scripts/citations.py --set-stage bert --set-step infer
uv run python scripts/citations.py --set-stage bert --set-step relabel
uv run python scripts/consolidate.py [--set-only embed_delta]
uv run python scripts/topics.py [--include-summaries]
```
