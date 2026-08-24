# 02-retrieval

Retrieval experiments: which papers reach the writer, and why.

## Experiments

```
02-01-subgraph-retrieval   whether the induced subgraph recovers the gold lineage
02-02-relevance-judge      how many landmarks the reader grades as unrelated
02-03-ancestor-gate        where the ancestor cosine floor belongs
02-04-selection-flags      what each retrieval toggle is worth on its own
02-05-reader-fusion        whether fusing cosine with the reader grade is Pareto
02-06-selection-objective  PPR against the set-coverage objectives
02-07-retrieval-breadth    the ef_search bug, and the coupled floor and budget package
```

## Running one

```sh
uv run python experiments/02-retrieval/<name>/run.py
```

Each experiment writes into its own `results/` and `report/`, and its README carries the
hypothesis and the conclusion. Raw runs under `results/runs/` are gitignored.
