# evaluate_retrieval

The four benchmarks that score a recipe. Each stage mines its own cases, writes one query per
case through Gemma, runs every recipe `config.toml` names for it, and leaves a directory that
replays on its own.

```
driver.py               the half every stage shares: mining, pooling, scoring, writing
stage0_surveymatch.py   one review, the key is its own references
stage1_frontiermatch.py two reviews in a leaf, the key is what the later one added
stage2_consensusmatch.py three reviews in a leaf, the key is what all three cite
stage3_precisionmatch.py no key, the judge is the topic tree plus the leaf's citation union
```

## Running one

```sh
uv run python scripts/evaluate_retrieval/stage0_surveymatch.py
```

Everything a stage needs is in `[retriever_eval]`: the sample count, the seed, the per-metric
floors and which recipes each metric compares. Mining is deterministic under `SEED`, and a
candidate is kept when the hash of its id falls under `SAMPLE_RATE`, so raising `MAX_SAMPLES`
grows the set rather than reshuffling it.

## What comes out

```
experiments/retrieve/{Metric}/
    run.log                     every line, console and file
    performance.png             one horizontal box per recipe
    {recipe}/config.toml        the benchmark settings and the recipe, copied verbatim
    {recipe}/scores.jsonl       one row per case
```

A row carries the query, the cutoff, the anchors, the whole answer key and the whole ranked
answer, so any statistic can be recomputed later without the store.

## Why it is not slow

Recipes that share a retrieval prefix share one pool, so six of them cost one retrieval.
`get_prefix` is what decides that, and a recipe changing only its exponents never triggers a
second pool. A query is 1.2s with the expanders and 0.7s without.
