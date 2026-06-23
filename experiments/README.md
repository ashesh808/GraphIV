# `experiments/` — numbered, self-contained ablations

Each experiment isolates **one lever** of the phase-6 research endpoint, drives it across ≥2 gold
topics, and reports a **vector** of metrics (never one number — any single metric is gameable; see
experiment-1). Every experiment is a small `run.py` over the shared harness plus a paper-style
`README.md` (hypothesis · what we test · why, cited to arXiv papers in our own corpus · how to
reproduce · results + ablation findings + caveats).

```
experiments/
  _harness/                 shared measurement instruments (ported from the pre-rewrite kg_rag_lab;
                            nothing here imports from .legacy)
    runner.py   driver.py   evaluate.py   metrics.py   topics.py   topics.json
    judge.py    faithfulness.py   vision_check.py   viz.py   theme.py   _llm.py   _boot.py
  experiment-<n>-<slug>/
    run.py                  declares the conditions / analysis; populates README.md from results/
    README.md               the write-up (auto-populated tables + figures)
    code/                   experiment-specific code not importable from the phases (optional)
    results/                summary.json (cache), metrics.md, *.png, runs/ (gitignored)
```

Everything reads the **single Postgres+pgvector store** (`./data/pg`); figures use the global theme
(`theme.py` → `theme.json` Material palette + Google Sans Flex). The topic battery is the editable
`_harness/topics.json` (≈27 CS topics incl. A-in-B compositional probes), not a hardcoded list.

## The instruments (`_harness/`)
- **metric vector** (`metrics.py`): frontier_count, 2025/2026 landmark counts, n_edges, grounded vs
  off_digest, words, `num_density` (digits/1k chars — specificity), judge scores, rounds, figures.
- **independent judge** (`judge.py`): Gemma-4-26B, 4 axes 1–5 (grounding/coverage/lineage/coherence),
  multi-pass averaged.
- **faithfulness** (`faithfulness.py`): samples single-cite claims, checks each against the cited
  paper's abstract (yes/partial/no) — the correctness tripwire.
- **vision caption-faithfulness** (`vision_check.py`): re-confirms each figure caption against its
  saved crop with Gemma-4-26B-Vision.
- **gold topics** (`topics.py`): canonical-set + spine recall for diffusion / transformer / test-time.

## Index

**Data / graph analyses (1–5)** — characterize the substrate, pure SQL over the store (no LLM):

| n | experiment | what it measures | path |
|---|---|---|---|
| 1 | Resolver quality | 5-layer resolution rate by method / category / era | `experiment-1-resolver-quality/` |
| 2 | Labeling quality | teacher prompt evolution + per-head confusion / PRF | `experiment-2-labeling-quality/` |
| 3 | Graph structure | degree distributions, intent/polarity mix, top hubs | `experiment-3-graph-structure/` |
| 4 | Clustering comparison | bisecting tree vs kmeans→DBSCAN vs HDBSCAN | `experiment-4-clustering-comparison/` |
| 5 | Topic tree | leaf size / depth / coherence; no-noise-bucket | `experiment-5-topic-tree/` |

**Phase-6 lever ablations (6–12)** — isolate one endpoint lever each, metric **vector** over the
topic battery (deep tiers drive the judge-loop):

| n | experiment | lever | path |
|---|---|---|---|
| 6 | Component ablation | remove {ppr, topic-tree, citation-graph, full-text} | `experiment-6-component-ablation/` |
| 7 | Recency knob | `recency ∈ {0,.2,.4,.6,.8}` | `experiment-7-recency-knob/` |
| 8 | frontier_pull | `no_frontier_pull` on/off | `experiment-8-frontier-pull/` |
| 9 | Judge-driven deep loop | `max_rounds ∈ {1,2,3}` | `experiment-9-judge-loop/` |
| 10 | Full-PDF critique depth | `critique_k ∈ {0,4,8}` | `experiment-10-critique-depth/` |
| 11 | Vision figures | `figures` on/off | `experiment-11-vision-figures/` |
| 12 | Deep-research dogfood | old single-pass vs full deep pipeline | `experiment-12-deep-dogfood/` |

## Headline findings (phase-6 levers, experiments 6–12)
- **No single metric can be trusted** (exp-1): `no_graph` *maximizes* frontier_count (78.5) while
  zeroing edges, recall, and judge score — a failure artifact. The full system is the only config
  that keeps every axis healthy. (faithfulness 0.94–1.0 throughout — a stable tripwire.)
- **Recency is a dial, not a quality axis** (exp-2): frontier 4→32 as the knob rises, but canonical
  recall collapses 0.81→0.17; `0.4` is the balance point.
- **frontier_pull is *the* 2026 mechanism** (exp-3): off → 2026 landmarks drop to exactly **0** at
  identical total frontier_count.
- **Inference-time compute helps, and the judge self-terminates** (exp-4): judge overall rises
  4.38 → 4.56 → 4.75 with rounds; at cap 3 the loop stops itself (avg rounds_run 1.5).
- **Full-PDF critique is a NULL result** (exp-5): no clear gain in grounding/specificity; partly an
  artifact of the abstract-only faithfulness checker penalizing full-text depth. Measured, not
  assumed — the cleanest "negative result" in the suite.
- **Vision is a clean additive win** (exp-6): 9 figures/topic at **0.89** caption faithfulness,
  off-digest *lower* with figures. Yes, leverage the vision model.
- **End-to-end the upgrade wins decisively** (exp-7): 2026 coverage **0 → 11**, length 855 → 3659
  words, +9 figures — while judge/faithfulness stay ≈flat (a longer recent review is harder to keep
  maximally tight than a short foundational one — again, read the vector).

## Reproduce
```bash
uv run python experiments/experiment-2-recency-knob/run.py     # cheap (~25 min)
uv run python experiments/experiment-4-judge-loop/run.py        # deep (~60-90 min, single 3090)
```
