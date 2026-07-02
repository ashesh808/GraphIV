# `experiments/` — staged, self-contained ablations

Each experiment isolates **one lever** and reports a **vector** of metrics (never one number — any
single metric is gameable; see `03-generation/03-02-component-ablation`). Experiments are grouped by
pipeline stage and numbered `0a-0b`, where `a` is the stage (1 preprocessing, 2 retrieval, 3
generation). `deep-research/` is the un-numbered flagship: the full deployed pipeline, dogfooded.

```
experiments/
  _harness/                 shared measurement instruments (ported from the pre-rewrite kg_rag_lab;
                            nothing here imports from .legacy)
    runner.py driver.py evaluate.py metrics.py topics.py topics.json
    judge.py faithfulness.py vision_check.py viz.py theme.py _llm.py _boot.py
    retrieval.py digest.py        canonical subgraph retrieval + adjacency digest
  cache/papers/{arxiv_id}/        global per-paper cache, reused across experiments (planned)

  0a-<stage>/0a-0b-<slug>/        every experiment follows this locked template:
    run.py            thin entry (--no-cache / topic args) → code/<module>.run()
    code/<module>.py  the logic (results/figures/tables written on run)
    cache/            per-experiment cache
    results/          metrics.json/md · ablation.png · table.tex · macros.tex · runs/ (gitignored)
    report/           report.md · report.tex · report.pdf
    readme.md         one-screen what / conclusion / how-to-run
```

Everything reads the **single Postgres+pgvector store** (`./data/pg`); figures use the global theme
(`theme.py`). The topic battery is the editable `_harness/topics.json` (≈27 CS topics incl.
A-in-B compositional probes). Lint gate: `ruff check experiments/ ; black experiments/ ; pyright
experiments/` — all clean. Each `code/` dir is registered in `pyrightconfig.json`.

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
| id | experiment | conclusion |
|---|---|---|
| 02-01 | subgraph-retrieval | committed PPR recipe recovers 0.74 canonical / 0.92 spine (≈87% of reachable) |
| 02-02 | relevance-judge | ~78% on-topic, but ~22% noise carries high in-degree (invisible to PPR) |
| 02-03 | ancestor-gate | **0.35 cosine floor is a Pareto win** (precision + recall both up) |
| 02-04 | selection-flags | **count doesn't matter** — cosine-gate and LLM-filter are independent flags |

### `03-generation/` — does the review come out good? (full pipeline → compose + judge)
| id | experiment | conclusion |
|---|---|---|
| 03-01 | judge-validity | the judge is sound on grounding/coverage; lineage weak; no position/verbosity bias |
| 03-02 | component-ablation | **read the vector, never one number** (`no_graph` tops frontier, zeroes edges/judge) |
| 03-03 | embedding-format | ship `asym_raw` — asymmetric encoding makes HyDE redundant |
| 03-04 | recency-knob | a control surface, not a winner — monotonic frontier↔lineage trade |
| 03-05 | frontier-pull | the only path to the 2026 corpus delta (1.9/topic vs 0), free |
| 03-06 | landmark-selection | the win is the filter, not the count |
| 03-07 | graph-representation | production digest = adjacency-list + extracted content + roles + alias |
| 03-08 | judge-loop | test-time compute works (pairwise 0.75, 6/0/2); the judge self-stops |
| 03-09 | critique-depth | a documented near-null — depth beyond ~4 adds cost, not quality |
| 03-10 | vision-figures | enrichment, not a text lever — value is caption-faithfulness (0.93) |
| 03-11 | hub-suppression | generic hubs (Attention 27/27) hijack niche reviews; no structural silver bullet → a compose guard removes them (3/1/3/1 → 0/0/0/0) at zero recall cost |

### `deep-research/` — the flagship (the deployed pipeline, dogfooded)
Old single-pass default vs the full deep pipeline (deep panel, n=8): pairwise **8/0/0 on grounding,
5/2/1 overall** — 9.0 2026-papers/topic (vs 0), 2.4× frontier, 5× length, 13 verified figures.
**This is what gets deployed.**

## Reproduce
```bash
uv run python experiments/02-retrieval/02-03-ancestor-gate/run.py        # retrieval, cheap
uv run python experiments/03-generation/03-08-judge-loop/run.py          # deep (~60-90 min, single 3090)
uv run python experiments/deep-research/run.py                           # the flagship before/after
```
