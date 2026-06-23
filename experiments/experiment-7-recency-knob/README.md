# experiment-2 — Topic-adaptive recency knob

## Hypothesis
A single scalar `recency ∈ [0,1]` should monotonically trade **historical lineage** (citation
edges, foundational papers) against **frontier coverage** (2025/2026 landmarks), *without* the
operator ever naming a cutoff year — the frontier year is detected per-topic from the pool's own
publication-year histogram (anchored to the current date).

## What we test
The lone independent variable is `recency` ∈ {0.0, 0.2, 0.4, 0.6, 0.8}. Everything else is held
constant: single-pass `fast` effort, `ppr` ranking, topic-tree refinement on, `frontier_pull` on.
Two topics (diffusion, test-time-compute); metrics are averaged across them.

`recency` sets the fraction of landmark slots reserved for the detected frontier band
(`recent_floor = round(recency * m)` in `phases/phase-6/components/recency.py`), filled
newest-cohort-first by `frontier_select`.

## Why (grounded in the corpus)
The motivating failure: a query literally asking for *recent advances* returned **0** papers from
2026 though the graph holds 151k embedded 2026 papers. Citation-count ranking structurally favors
old hubs — a 2026 paper has had weeks, not years, to accrue citations — exactly the
in-degree-vs-age tension that test-time-compute scaling work also reasons about for *evidence*
recency (e.g. compute-optimal inference, arXiv:2408.03314). A recency control lets the user pick a
"frontier brief" vs a "full lineage review" per query.

## How to reproduce
```bash
uv run python experiments/experiment-2-recency-knob/run.py
```
Outputs land in `results/`: `metrics_raw.json` (per topic×condition), `metrics.json` +
`metrics.md` (mean per recency), `ablation.png`.

## Results
Mean over 2 topics (diffusion, test-time-compute); full table in `results/metrics.md`, plot in
`results/ablation.png`.

| recency | frontier_count | ge_2025 | n_2026 | grounded | off_digest | landmark_recall |
|---|---|---|---|---|---|---|
| 0.0 | 4.0 | 1.5 | 1.0 | 21.5 | 0.0 | **0.81** |
| 0.2 | 9.5 | 5.5 | 2.5 | 23.5 | 0.0 | 0.81 |
| 0.4 | 16.0 | 9.0 | 5.0 | 19.0 | 0.5 | 0.65 |
| 0.6 | 24.0 | 13.0 | 6.5 | 21.0 | 0.5 | 0.29 |
| 0.8 | 32.0 | 18.0 | 9.0 | 21.0 | 0.0 | **0.17** |

Frontier coverage rises **monotonically and strongly** (frontier_count 4→32, 2026 landmarks 1→9),
while **canonical recall collapses** (0.81→0.17) as recent low-citation papers displace foundational
hubs. `grounded` stays ~19–24 and `off_digest` ≈ 0 throughout — the knob shifts *which* papers are
surfaced, never the grounding. (`n_edges` is pool-level and ~constant; the lineage loss shows up in
recall, not edge count.)

## Ablation finding & caveat
Confirmed: `recency` is a clean dial between two legitimate report shapes, **not** a quality axis —
chasing `frontier_count` to the maximum (`recency=0.8`) costs you the foundational lineage
(`recall` 0.81→0.17). The default `0.4` is the balance point: meaningful frontier (16 landmarks, 5
from 2026) while still recovering ~⅔ of the canonical foundations. Read the vector, not one number.

## Ablation finding & caveat
Read the vector, not one number (the eval.md lesson): a high `frontier_count` at `recency=0.8` is
only good *if* `n_edges` stays non-trivial — otherwise the review is a flat list of recent papers
with no origins→frontier story. The knob is a dial between two legitimate report shapes, not a
quality axis.
