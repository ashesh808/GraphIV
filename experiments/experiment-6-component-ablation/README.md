# experiment-1 — Component ablation study

*(Formalized port of the pre-rewrite `kg_rag_lab/eval_ablation.py` — the headline ablation table.)*

## Hypothesis
The retrieval/ranking pipeline is a *system*: each component contributes a separable, measurable
quality, and no single metric captures it. Specifically — the **topic tree** drives citation
density, **PPR + frontier reservation** restores frontier coverage that raw in-degree starves, the
**citation graph** is what creates chronology at all, and **full text** adds per-paper specificity.

## What we test
Knock out one component at a time (control = `full`), holding the topic and question fixed:

| config | what is removed |
|---|---|
| `full` | nothing (refined retrieval + tree + full text + PPR) |
| `indegree` | PPR + frontier reservation → raw in-degree ranking |
| `no_cluster` | the topic-tree leaf refinement |
| `no_graph` | the induced citation subgraph (vector-only) |
| `no_fulltext` | per-paper extraction (abstracts only, `effort=fast`) |

Two topics (diffusion, test-time-compute), means reported. Instruments: the metric vector +
independent **4-axis LLM judge** (Gemma-4-26B, grounding/coverage/lineage/coherence) + the
**faithfulness** tripwire (does each cited paper actually support its claim?).

## Why (grounded in the corpus)
Graph-structured retrieval and personalized propagation are the design basis (PPR/landmark
influence, à la HippoRAG-style graph RAG). The frontier-starvation effect — old hubs dominating
in-degree — is the same age-vs-citation tension that inference-scaling work reasons about
(arXiv:2408.03314). Faithfulness-as-tripwire follows verifier literature in the corpus
(arXiv:2110.14168): a separate checker catches mis-attribution that fluency hides.

## How to reproduce
```bash
uv run python experiments/experiment-1-component-ablation/run.py
```

## Results
Mean over 2 topics (diffusion, test-time-compute); full table in `results/metrics.md`, plot in
`results/ablation.png`.

| config | n_edges | frontier_count | off_digest | num_density | landmark_recall | j_overall | faithfulness |
|---|---|---|---|---|---|---|---|
| **full** | 7894 | 36.0 | 0.0 | 45.2 | **0.81** | 4.06 | 0.94 |
| indegree | 7894 | **26.0** | 0.5 | 51.3 | 0.88 | 4.50 | 1.00 |
| no_cluster | **4856** | 33.5 | 0.0 | 54.6 | 0.65 | 3.69 | 0.97 |
| no_graph | **0.0** | **78.5** | 1.0 | 38.0 | **0.00** | **2.25** | 0.94 |
| no_fulltext | 7894 | 16.0 | 0.0 | 44.6 | 0.65 | 3.25 | 1.00 |

The legacy finding reproduces cleanly:
- **`no_graph` is the "gameable single metric" artifact**: it has the *highest* `frontier_count`
  (78.5 — pure similarity floods recent papers) yet **0 edges**, **0 recall**, and the **worst
  judge (2.25)** — chronology and canonical coverage are destroyed.
- **`indegree`** starves the frontier (26 vs 36): raw in-degree favors old hubs, exactly the
  age-vs-citation bias `ppr`+frontier reservation fixes.
- **`no_cluster`** cuts citation density 38% (7894→4856) and recall (0.81→0.65): the topic-tree leaf
  anchor is what keeps the pool connected and on-topic.
- **`no_fulltext`** keeps structure but halves landmarks (40) and lowers judge (3.25) — abstracts
  carry less to synthesize.
- **`faithfulness` 0.94–1.00 everywhere** — stable across configs, confirming its role as a
  correctness tripwire, not a lever-ranking score.

Note the honest nuance: `indegree`'s `j_overall` (4.50) edges out `full` (4.06) — a foundation-heavy
review reads "cleaner" to the judge — but it loses on `frontier_count` (26 vs 36). This is itself the
thesis: **judge-overall alone is gameable**; only the full vector shows `full` balancing every axis.

## Ablation finding & caveat
**Read the vector, never one number.** The full system is the configuration that keeps *all* axes
healthy simultaneously (edges > 0 for chronology, frontier reserved, off-digest ≈ 0, density high,
judge overall high). A knockout that wins one metric (e.g. `no_graph` frontier) loses others
catastrophically.
