# 01-preprocessing

Preprocessing experiments: how well the graph gets built, before any question is asked.

## Experiments

```
01-01-resolver-quality       how often a reference resolves to the right arXiv id
01-02-labeling-quality       how well the teacher and the student label citation intent
01-03-graph-structure        what the resulting citation graph actually looks like
01-04-clustering-comparison  which clustering the topic tree should be built on
01-05-topic-tree             whether the density-aware tree beats a uniform grid
01-06-prompt-refinement      what the APE loop does to the teacher's labeling policy
01-07-student-classifier     how well the distilled student labels, and what it changed
```

## Running one

```sh
uv run python experiments/01-preprocessing/<name>/run.py
```

Each experiment writes into its own `results/` and `report/`, and its README carries the
hypothesis and the conclusion. Raw runs under `results/runs/` are gitignored.
