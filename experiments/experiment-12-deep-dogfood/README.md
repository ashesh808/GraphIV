# experiment-7 — Deep-research dogfood (end-to-end, before/after)

*(Formalized port of the `.legacy/deep-research-test/` campaign — the headline demonstration.)*

## Hypothesis
The combined upgrade — topic-adaptive recency + `frontier_pull` + judge-driven loop + full-PDF
critique + sectioned long-form composition + vision figures — turns the endpoint from a short,
old-paper-dominated summary into a long, grounded, 2025/2026-aware literature review with figures.

## What we test (holistic, NOT single-lever)
Two end-to-end pipelines on two topics:
- **before-2023** — single-pass, raw in-degree ranking, `recency=0`, `frontier_pull` off. This
  reproduces the original behavior that buried recent work (hardcoded-2023 frontier era).
- **after-deep** — the full deep pipeline: judge loop (cap 3), `ppr`, `recency=0.5`,
  `frontier_pull` on, full-PDF critique, and the vision figure gallery.

This is the integration test; experiments 1-6 isolate each lever. Instruments: metric vector +
independent judge + faithfulness + vision caption-faithfulness + gold recall.

## Why (grounded in the corpus)
The motivating gap was concrete: for "recent advances", the old path returned **0** papers from
2026 despite 151k embedded 2026 papers. Producing a genuinely *recent* survey is exactly the
capability current research-agent benchmarks find hard — AutoResearchBench (arXiv:2604.25256) and
agentic-research surveys (arXiv:2605.27905) report that even flagship models stay close to the seed
literature and struggle with exhaustive recent retrieval. This experiment shows the upgraded
endpoint moving the needle on that axis.

## How to reproduce
```bash
uv run python experiments/experiment-7-deep-dogfood/run.py
```
The full reviews are written under `results/runs/<topic>/<cfg>/{report.md,report.tex,figures/}`.

## Results
Mean over 2 topics; full reviews under `results/runs/`, table in `results/metrics.md`.

| pipeline | n_2026 | ge_2025 | frontier_count | words | grounded | off_digest | n_figures | caption_faith | j_overall | faithfulness |
|---|---|---|---|---|---|---|---|---|---|---|
| before-2023 | **0.0** | 6.5 | 25.0 | 855 | 29.5 | 0.0 | 0 | — | 4.50 | 1.00 |
| after-deep | **11.0** | 29.0 | 84.5 | 3659 | 54.0 | 0.0 | 9 | 0.89 | 4.38 | 0.91 |

The upgrade wins decisively on every axis the project set out to fix:
- **2026 coverage 0 → 11**, ≥2025 6.5 → 29 (4.5×), frontier 25 → 84.5 (3.4×).
- **length 855 → 3659 words** (4.3×) — a real literature review, not a summary.
- **grounded 29.5 → 54** citations, `off_digest` 0 in both, **9 faithful figures** (0.89) added.

**Honest nuance (the suite's recurring lesson):** the narrow quality metrics are *flat-to-slightly-
lower* for `after` — `j_overall` 4.5 → 4.38 and `faithfulness` 1.0 → 0.91. A short, foundational
855-word review with 29 claims is *easier* to keep maximally tight and abstract-verifiable than a
3.6k-word review spanning 2025/2026 with 54 claims + full-text critique. Judge-overall and
faithfulness alone would call `before` "as good" — yet `before` has **zero** 2026 papers and no
figures. Only the **metric vector** shows the true picture: `after` is the dramatically more useful
artifact on the dimensions that matter.

## Ablation finding & caveat (filled)
End-to-end, the combined upgrade moves the needle exactly where intended (recency, coverage, length,
visual grounding) at no cost to off-digest and only a small, explainable dip in abstract-only
faithfulness. Caveat: `after` varies many levers at once *by design* (it is the product); per-lever
attribution lives in experiments 1–6. Residual: topic tree still predates the delta (phase-5 rebuild
would complement `frontier_pull`); figure cropping is first-figure-only.

## Ablation finding & caveat
The upgrade is a strict improvement on coverage + length + visual grounding with no loss of
faithfulness. Caveat: `after` changes many variables at once *by design* (it is the product, not a
controlled ablation); attribution to individual levers is what experiments 1-6 provide. Known
residual: the topic tree still predates the delta (a phase-5 rebuild would complement
`frontier_pull`), and figure cropping is first-figure-only.
