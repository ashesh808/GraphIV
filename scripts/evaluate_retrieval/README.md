# evaluate_retrieval

Runs the four benchmarks that score a recipe, which [`docs/benchmarks.md`](../../docs/benchmarks.md) defines.
Each stage reads one split of the published benchmarks and scores every recipe `config.toml` lists for that benchmark, and the directory it leaves can be replayed on its own.
The cases and their questions come from `graphiv-benchmarks-<cutoff>/` under `[export] EXPORT_PATH`, which `scripts/export/stage2_export_benchmarks.py` writes, so a run calls no model.

```
driver.py                 the part every stage shares: mining, pooling, scoring and writing
stage0_surveymatch.py     one review, whose answer is its own references
stage1_frontiermatch.py   two reviews in one leaf, whose answer is what the later one added
stage2_consensusmatch.py  three reviews in one leaf, whose answer is what all three cite
stage3_precisionmatch.py  the SurveyMatch cases with no answer key, with the topic tree and the leaf's citations judging what is on topic
```

## Running One

```sh
uv run python scripts/evaluate_retrieval/stage0_surveymatch.py
```

`[retriever_eval] SPLIT` picks the split: train to tune on, val to choose, test to report.
`MAX_SAMPLES` caps how many cases of it a run reads, every case at 0, and `[benchmarks] CUTOFF` picks the version.

## What Comes Out

```
experiments/retrieve/{Metric}/
    run.log                     every line, console and file
    performance.png             one horizontal box per recipe
    {recipe}/config.toml        the benchmark settings and the recipe, copied verbatim
    {recipe}/scores.jsonl       one row per case
```

Each row carries the query, the cutoff, the anchors, the whole answer key and the whole ranked answer, so any statistic can be recomputed later without the store.

## Why It Is Fast

Recipes that share a retrieval prefix share one pool, so six of them cost one retrieval, and a recipe that only changes exponents never builds a second pool.
A query takes 1.2 s with the expanders and 0.7 s without.
