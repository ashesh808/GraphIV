# Plan — single-store consolidation + research-grade experiment suite

> Living plan doc. Mirrors the approved plan at
> `~/.claude/plans/i-d-like-to-go-replicated-clover.md`. Sequencing: **DB migration first**, then
> experiments, then the paper layer. Goal: ship an open, reproducible, intent-typed dual-graph arXiv
> KG + grounded review endpoint as a **full research paper / resource** so others can contribute.

## Architecture decision: ONE store = Postgres + pgvector

Graph algorithms are already Python-side (`pagerank.py`, `subgraph.py`), so Neo4j is only a vector
index + 1–2-hop fetcher — both replaceable by pgvector + SQL. The ~500GB is dominated by Postgres
**parse-scratch text** (`sentence`, `paragraph`, `raw_bib_text` over 173M rows); the graph itself
(edges + intents + embeddings + metadata) is small → a slim distributable dump is **plausibly
sub-100GB**.

- **Canonical store:** Postgres + pgvector (build + serve).
- **Neo4j:** optional one-way export (derived view) for Bloom exploration + the graph-structure
  experiment. Off the serve path; nobody is forced into a JVM.
- One decision still open to revisit: Neo4j-native instead. Default assumed = Postgres+pgvector.

# Fixes (DB migration — DO FIRST)

Move every project DB from globally-running NixOS processes to **per-project, flake-provisioned**
services, with all data mounted under `./data` by symlink (like `data/pdf` → `/mnt/Vault-Storage/
research/arxiv/pdfs` and `data/html` today). Only the llama.cpp endpoint stays external.

Storage: `/Vault` = fast 1TB PCIe (live DB datadir); `/mnt/Vault-Storage/research/arxiv` = 10TB ZFS
HDD (bulk/cold: pdf, html, raw npy).

- **A1.** Postgres becomes the one store (+`pgvector`): `paper` metadata (from SQLite `arxiv.db`),
  `citation` (intents/polarity), `paper_embedding` `vector(768)`/`halfvec` + HNSW cosine (replaces
  Neo4j `paper_emb`), `paper_topic`/`leaf` (from `topic_tree_nomic.db`). Split heavy parse-scratch
  text into its own table so the shippable dump can exclude it.
- **A2.** Migrate metadata + nomic embeddings into PG (repurpose `phases/phase-4/components/*` to
  pgvector). **Alignment spot-check** baked in (recompute nomic on a sample, assert cosine≈1) — fixes
  the silent embedding↔id corruption risk.
- **A3.** Rewrite the phase-6 **retrieval fetch layer only** (`retrieve.py`, `retrieval_refined.py`):
  Cypher/Neo4j-vector → SQL/pgvector. `pagerank.py`, `subgraph.py`, `recency.py`, `frontier_rank.py`,
  compose/judge/critique/figures stay untouched.
- **A4.** `flake.nix`: project-scoped Postgres+pgvector, datadir on `/Vault`, symlinked into `./data`.
  Rotate + flake-provision secrets; plaintext password leaves tracked config.
- **A5.** Optional `phases/phase-4` Neo4j-export component (builds Neo4j from Postgres on demand).

# Experiments

Structure each as a single lever / analysis with a metric **vector** (never one number). Build the
new phase-3/4/5 analysis experiments first, then re-run the existing phase-6 levers on the full topic
battery.

- **E1 — 5-layer resolver:** re-explain each layer; figures of **resolution success by topic /
  category / era** (full-corpus stats pass first; current `citation_stats/summary.json` is a partial
  612k run). Per-layer contribution + rejection reasons.
- **E2 — labeling (Gemma → BERT):** prompt **evolution** (length + what each v1→v6 added) and label
  quality as **per-class confusion + precision/recall/F1, per classifier head** (intent 6-way,
  polarity 3-way). Stage-1 now on the existing test split; **stage-2 human-gold deferred to the very
  end** (see Phase C labeling tool).
- **E3 — graph structure viz:** degree distributions, components, category-mix, temporal growth
  (port `.legacy/scratchpad/graph/analyze*.py`).
- **E4 — clustering comparison:** the shipped density-aware bisecting tree vs the **old
  kmeans-kmeans→DBSCAN-resweep + LLM-labeled parents** vs ≥1 more (e.g. HDBSCAN), on coherence /
  no-noise-bucket / downstream retrieval edges. We can do a lot more on clustering — explore it.
- **E5 — topic-tree viz + analysis:** leaf-size/depth/coherence distributions, 2D projection,
  example leaves.
- **E6+ — existing phase-6 levers** (component ablation, recency, frontier-pull, judge-loop,
  critique-depth, vision, deep-dogfood) re-run on the topic battery, with explicit discussion of
  graph-use and frontier-vs-non-frontier.

There should be a LOT of experiments — breadth across topics + ablations is what makes it
research-worthy.

## Topic battery

Replace the 3 frozen gold topics with a **transparent, configurable 20–30 topic list** (an editable
`topics.json`) spanning CS at varying specificity, including the **A-in-B compositional design**
(fix application A vary method B; then fix B vary A). **I seed + run it now; edit later anytime.**
Representative seed:

- *Foundational:* transformer attention, diffusion models, GNNs, deep RL, contrastive learning, MoE,
  state-space models (Mamba).
- *Frontier:* test-time compute & reasoning, LLM agents/tool use, preference optimization (RLHF/DPO),
  long-context, speculative decoding, RAG.
- *A fixed, B varies:* diffusion for {video, audio, molecular generation}; transformers for {time
  series, code, protein structure}; GNNs for {drug discovery, recommendation, combinatorial opt}.
- *B fixed, A varies:* {diffusion, RL, transformers} for autonomous driving; {transformers, GNNs, RL}
  for program synthesis / theorem proving.

# Structure

```
experiment-N/
    run.py        # idempotent; pulls from existing DB / phase result/ where possible;
                  #   populates README.md with the tables + images it writes to results/
    README.md     # imports results (tables + images) straight from results/
    code/         # experiment-specific code not importable from the phases
    results/      # destination for figures + tables (heavy runs/ gitignored; showcase/ tracked)
```

# Visualization

Global theme: load `./theme.json` (dark/light Material palettes already present); font = **Google
Sans Flex**. Refactor `experiments/_harness/viz.py` inline hex into a shared theme module used by all
experiment + phase figures.

# Intermediate results

Each phase gets `phases/phase-N/result/` that logs history (resolution stats, label runs, tree
stats…) which experiments import as their inputs.

# Implementation

Temporary / probe code → `scratchpad/`. Shippable code → the phase / experiment tree.

# Phase C — paper layer (toward the full paper)

- **Baselines** in `_harness`: STORM-style (pure retrieval) + GraphRAG-style (LLM-extracted graph),
  to test "citation-graph grounding beats both on faithfulness / recency / lineage".
- **Evaluation contribution:** formalize lineage/developmental metrics (spine/main-path recall,
  chronological faithfulness, frontier coverage); the A-in-B battery is itself an eval-design novelty.
- **Human-eval** (N≈15–20) vs baselines.
- **Gold-label tool (very last step):** a doom-scrollable **web labeling tool** (FastAPI/Flask + one
  HTML page over PG) to hand-label **~1000** citations with intent (6) + polarity (3) → `gold_label`
  table → E2 stage-2 human-gold per-class PRF for teacher + student.
- **Resource release:** sub-100GB `pg_dump` + reproducible builder + the gold benchmark + leaderboard.
- **Positioning:** drop "first open arXiv KG" (OpenAlex / S2ORC / OpenCitations / unarXive exist).
  Claim: *first intent-typed, recency-aware, dual-graph arXiv KG + grounded developmental-review
  endpoint, single-store + single-box reproducible, with an open edge-quality benchmark.*
