# miner

A list of papers into what the field argues with, how it got there, and what has answered it
since. Nothing here takes a question, so the caller decides which papers are worth mining and this
decides what they mean together.

```
leyline.py   LeyLine, the algorithm on a typed graph, which knows nothing about papers
miner.py     Miner, which knows what a paper is and calls LeyLine once
reader.py    the six-role grade, the only model call in the package
era.py       where a field's current era starts, read off its own dates
rank.py      the area gate, and citations per year blended with the reader
store.py     every statement this package sends to Postgres
recipe.py    the [miner] block, which is where every constant lives
```

## Why LeyLine takes no papers

It takes a typed edge list, a score per node, an order per node and a weight per edge type. That
is the whole input, so `tests/miner/test_leyline.py` runs it on a hand-built ten-node graph with
no store, no endpoint and no GPU. Everything that knows an arXiv id from a commit hash is in
`miner.py`.

## What a call does

```python
found = Miner(dsn, graph, read_recipe("retrieval_recipes/survey.toml")).mine(papers, vector, asked)
```

The list is expanded one citation hop first, because papers a reader kept rarely cite each other
and the papers a field argues with are the ones they all cite. The walk then runs on the head of
the list and the forward look runs on all of it, since the two pull opposite ways: lineages stop
reproducing once the graph is too wide, and successors keep scaling with every paper added.

| what comes back | what it is |
| --- | --- |
| `magnets` | the papers the list takes positions on, with the counts per intent |
| `lineages` | dated paths through the graph, and how many runs reproduced each |
| `disputes` | one sentence per citing pair that took a position |
| `successors` | papers from the recent window citing the list, which need no citations of their own |
| `connectors` | papers that are not in the list but sit on a path between two that are |
