# `experiments/` — staged, self-contained ablations

Each experiment isolates **one lever** and reports a **vector** of metrics (never one number — any
single metric is gameable; see `02-retrieval/02-04-fusion-rule`). Experiments are grouped by
pipeline stage and numbered `0a-0b`, where `a` is the stage (1 preprocessing, 2 retrieval, 3
generation). `deep-research/` is the un-numbered flagship: the full deployed pipeline, dogfooded.

```
experiments/
  _harness/                 shared measurement instruments (ported from the pre-rewrite kg_rag_lab;
                            nothing here imports from .legacy)
    runner.py driver.py evaluate.py metrics.py topics.py topics.json
    judge.py faithfulness.py vision_check.py viz.py theme.py _llm.py _boot.py
    retrieval.py digest.py        canonical subgraph retrieval + adjacency digest
    README.md                     what each instrument measures
  cache/papers/{arxiv_id}/        global per-paper cache, reused across experiments (planned)

  0a-<stage>/0a-0b-<slug>/        every experiment follows this locked template:
    run.py            thin entry (--no-cache / topic args) → code/<module>.run()
    code/<module>.py  the logic (results/figures/tables written on run)
    cache/            per-experiment cache
    results/          metrics.json/md · ablation.png · table.tex · macros.tex · runs/ (gitignored)
    report/           report.md · report.tex · report.pdf
    README.md         one-screen what / conclusion / how-to-run
```

Everything reads the **single Postgres+pgvector store** (`./data/pg`); figures use the global theme
(`theme.py`). The topic battery is the editable `_harness/topics.json` (≈27 CS topics incl.
A-in-B compositional probes). Lint gate: `ruff check experiments/ ; black experiments/` — all clean. Tool config lives in `pyproject.toml`.

## The instruments (`_harness/`)
- **metric vector** (`metrics.py`): frontier_count, 2025/2026 counts, n_edges, grounded vs off_digest,
  words, `num_density` (specificity), judge scores, rounds, figures.
- **independent judge** (`judge.py`): Gemma-4-26B, 4 axes 1–5 + order-debiased pairwise + role labels.
- **faithfulness** (`faithfulness.py`) and **vision caption-faithfulness** (`vision_check.py`): tripwires.
- **gold topics** (`topics.py`): canonical-set + spine recall for diffusion / transformer / test-time.

## Index

### `01-preprocessing/` — characterize the substrate (pure SQL over the store, no LLM)
| id | experiment | what it measures |
|---|---|---|
| 01-01 | resolver-quality | 5-layer citation resolution rate by method / category / era |
| 01-02 | labeling-quality | teacher prompt evolution + per-head confusion / PRF |
| 01-03 | graph-structure | degree distributions, intent/polarity mix, top hubs |
| 01-04 | clustering-comparison | bisecting tree vs kmeans→DBSCAN vs HDBSCAN |
| 01-05 | topic-tree | leaf size / depth / coherence; no-noise-bucket |

### `02-retrieval/` — does the right paper come back? (retrieval metrics, no compose)

Rebuilt 2026-08-27 on the survey-qrels benchmark: 60 externally-authored answer keys in place of
the 3 hand-curated gold topics the old 02-01..02-07 rested on. The old notebooks are in git history
at `3326281`.

| id | experiment | conclusion |
|---|---|---|
| 02-01 | benchmarks | our BM25 reproduces LitSearch's published 50.0/39.9 exactly; our reader rerank beats GritLM-7B at 75.8/74.7; the graph signal inverts on their task |
| 02-02 | pool-construction | **half the gold never reaches the pool** and no knob recovers it; the only lever that moves the answer is graph admission, already at its optimum |
| 02-03 | signal-quality | graph and reader tie at 2.9x lift and disagree: 160 gold papers only the graph sees, 159 only the reader; a fifth of the pool carried an RRF score instead of a cosine, **fixed and shipped** |
| 02-04 | fusion-rule | the combining rule barely matters (8 smooth rules span 18 papers); **the input does** (39 papers from swapping cosine for citations-per-year) |
| 02-05 | selection-objective | fusion 336 > graph 305 > text 208 > set coverage 196; PPR beats set coverage and loses to fusion |
| 02-06 | leyline | the quota's 8 picks hit gold 1.73x as often as the slots they take, at 3 years old vs 7; both walk limits are load-bearing |
| 02-07 | frontier-reach | the reservation is free to ~32 slots: +343 recent picks for 1 dev paper; it is a control surface, not a setting with a right answer |

### `03-generation/` — does the writer make things up? (full pipeline -> compose + judge)

One metric throughout: whether a sentence in a finished report is backed by a paper.

| # | name | finding |
| --- | --- | --- |
| 03-01 | attribution | about seven in ten cited sentences are supported (0.714 Gemma, 0.744 Qwen), agreeing on 90.6% of sentences, kappa 0.762 |
| 03-02 | checker-validity | the checker approves 15-20% of deliberately broken citations against 71-74% of real ones, a gap of 0.55 both judges reproduce |
| 03-03 | graph-digest | the graph does not improve reliability: support 0.707 with it against 0.754 without, no-graph ahead in 8 of 10 matched pairs |
| 03-04 | source-coverage | 818 of 1372 sentences carry a citation (0.596), counted without a model |

Read 03-02 before 03-01: a support rate means nothing until the checker is shown able to reject.

How many *uncited* sentences invent something is not measured. Two label schemes both failed to
survive a second judge (five labels 37 against 67; one yes-or-no question 12 against 91, kappa
0.003). A cited sentence has a document to check against and an uncited one has only the
reader's threshold, so splitting those 554 sentences needs human labels.

Eleven earlier experiments measured levers rather than reliability and mostly rested on a
27-topic battery that is no longer trusted. They stay in the tree until their findings are
folded into `docs/decisions.md`.

### `deep-research/` — the flagship (the deployed pipeline, dogfooded)
Old single-pass default vs the full deep pipeline (deep panel, n=8): pairwise **8/0/0 on overall AND
grounding**, judged untruncated and confirmed unanimously by two disjoint-family judges — 9.0
2026-papers/topic (vs 0), 2.4× frontier, 5× length, 13 verified figures. **This is what gets deployed.**

## Reproduce
```bash
uv run python experiments/02-retrieval/02-03-ancestor-gate/run.py        # retrieval, cheap
uv run python experiments/03-generation/03-01-attribution/run.py         # reads a cache, instant
uv run python experiments/deep-research/run.py                           # the flagship before/after
```
