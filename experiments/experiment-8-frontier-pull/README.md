# experiment-3 — Leaf-independent `frontier_pull`

## Hypothesis
The newest papers (2026) can only enter the retrieval pool through a **leaf-independent** vector
pull. The topic tree (`topic_tree_nomic.db`) was built on the pre-delta corpus and has **0 rows
for 2026**, so the leaf-restricted recency injection structurally cannot reach 2026 work. Disabling
`frontier_pull` should therefore drop 2026 coverage toward zero while older-frontier counts barely
move.

## What we test
One variable: `no_frontier_pull` ∈ {False (on), True (off)}. Held constant: single-pass `fast`
effort, `ppr`, `recency=0.6`, two topics. `frontier_pull`
(`phases/phase-6/components/retrieval_refined.py`) queries the Neo4j `paper_emb` vector index with
a `year >= frontier_year` filter and merges the nearest recent papers, bypassing leaf membership.

## Why (grounded in the corpus)
This is a retrieval-coverage question: a paper invisible to retrieval can never be ranked or cited,
no matter how good the ranker. The diffusion frontier alone has 8,880 embedded 2025+ papers; the
tree simply doesn't index the 2026 cohort yet. (Independent confirmation in our own dogfood: a
research-agent benchmark in the corpus, arXiv:2604.25256, frames exhaustive *recent* retrieval as a
distinct, hard capability — "Wide Research" — that flagship models score <10% on.)

## How to reproduce
```bash
uv run python experiments/experiment-3-frontier-pull/run.py
```

## Results
Mean over 2 topics (single-pass, fast, recency=0.6); full table in `results/metrics.md`.

| frontier_pull | n_2026 | ge_2025 | frontier_count | n_landmarks | grounded | landmark_recall |
|---|---|---|---|---|---|---|
| **on** | **6.5** | 13.0 | 24.0 | 40 | 22.0 | 0.29 |
| **off** | **0.0** | 9.0 | 24.0 | 40 | 24.5 | 0.29 |

Decisive: turning `frontier_pull` off drops 2026 landmarks to **exactly 0** (per-topic: diffusion
5→0, test-time 8→0), while `frontier_count` is *identical* (24) — the reservation simply backfills
with 2024/2025 papers it can reach through the (pre-delta) topic tree. `ge_2025` also drops (13→9).
`n_landmarks`, `grounded`, and `landmark_recall` are otherwise unchanged, isolating the pull as the
single mechanism that surfaces leaf-less 2026 work.

## Ablation finding & caveat
`frontier_pull` is a *retrieval* fix, not a ranking fix; it is complementary to a future phase-5
topic-tree rebuild (which would let leaf-restricted injection reach 2026 natively). It is the
minimal change that closes the 2026 gap today without a multi-hour re-clustering job.
