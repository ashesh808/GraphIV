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

---

## Bugs the suite found

| bug | status | cost |
| --- | --- | --- |
| pool `.score` mixed RRF and cosine scales | **fixed and shipped** in `hybrid_pool` | 20.7% of every pool sat ~100x too low; those were the *better* papers (5.7% gold vs 3.9%, reader relevance 1.03 vs 0.47). Worth +69 to the text signal, +16 to ppr, +11 to trajectory, +0 to joint |
| `plainto_tsquery` ANDs every term | open, decision pending | lexical channel returns zero rows for all 60 surveys and all 597 LitSearch queries. Repairing it with OR **costs 11 papers**; deleting it gains 3 |
| `hnsw.ef_search` unset, capped at 40 | fixed earlier | 12 papers of 1617, much smaller than believed |
| `dominant_group` / `group_of` dead | open, delete them | none: it was the OLD coarse archive anchor, explicitly superseded by the topic-tree leaf anchor in `refined_pool`. Never wired even at `72fd50e`. The `hybrid.py` docstring describes a replaced mechanism, not a lost one |

---

## Claims this suite overturned

- "PPR is vindicated" (old 02-06): holds against set coverage, **fails against fusion**. Also
  measured while a fifth of every pool was mis-scored on the number PPR seeds from.
- "The graph is the weak signal, the reader is strong": wrong, they tie at 2.9x.
- "`ef_search` at 40 was catastrophic": 12 papers of 1617.
- "Fixing the lexical bug is a win": it is an 11-paper regression.
- "joint won because it dropped the frontier reservation": no, the reservation is worth 0-2 papers.
  The win came from the fused score. The two levers are independent.
- "Blending beats multiplication": they tie within 2 papers.
- "LeyLine hits 42.7% vs 30.2%": that was the loose any-mention key. On the suite standard it is
  18.1% vs 10.4%, and the ratio is better, 1.73x vs 1.40x.
- The shipped ancestor floor is **0.30**, not the 0.35 the deleted 02-03 README claimed.

The frozen pools these arms sweep live in `_harness/pools`, one pickle per survey, built once by
`_harness/bench/battery60.py` so the reader grades every survey exactly one time.
`_harness/bench/parity.py` checks the selector registry against the pre-refactor rankers over
all sixty.
