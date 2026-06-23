# experiment-5 — Full-PDF critique depth

## Hypothesis
Reading the **full text** of a paper (not just its abstract or salient snippets) and writing a
structured critique lets the review make more *specific, verifiable* claims — numbers, named
limitations, real comparisons — raising specificity and grounding, with returns that flatten as the
most-important papers are already covered.

## What we test
One variable: `critique_k ∈ {0, 4, 8}` — how many key papers (top in-degree + most recent) get a
full-PDF peer critique folded into the digest. Held constant: deep path, `max_rounds=2`, figures off,
two topics. Independent judge (esp. grounding) + faithfulness + `num_density` (digits per 1k chars).

## Why (grounded in the corpus)
Verification and process-level supervision raise reasoning quality in the literature: training
**verifiers** to check candidate solutions scales better than more fine-tuning (arXiv:2110.14168),
and **process reward models** (Math-Shepherd, arXiv:2312.08935) supervise intermediate steps rather
than only outcomes. The critique stage is the analogous move for *review writing* — a per-paper
read-and-check that supplies concrete evidence the abstract omits.

## How to reproduce
```bash
uv run python experiments/experiment-5-critique-depth/run.py
```

## Results (a NULL / mixed result — documented honestly)
Mean over 2 topics (deep path, max_rounds=2, figures off); full table in `results/metrics.md`.

| critique_k | n_critiques | num_density | grounded | j_grounding | j_coverage | j_overall | faithfulness |
|---|---|---|---|---|---|---|---|
| 0 | 0.0 | **39.6** | **46.5** | **4.75** | 3.75 | **4.38** | **1.00** |
| 4 | 3.5 | 37.3 | 44.0 | 4.50 | 3.50 | 4.12 | 0.75 |
| 8 | 7.0 | 38.0 | 40.0 | 4.50 | **4.00** | 4.25 | 0.84 |

**The hypothesis did NOT hold.** Adding full-PDF critique did not raise specificity or grounding;
if anything it slightly *lowered* `num_density` (39.6→38), `grounded` (46.5→40), `j_grounding`
(4.75→4.5), and `faithfulness` (1.0→0.75/0.84). The one gain is `j_coverage` at k8 (3.75→4.0) —
critique adds some analytical breadth.

Why (two effects, both real):
1. **Measurement artifact**: `faithfulness` checks each claim against the cited paper's *abstract*.
   Critique deliberately surfaces *full-text* facts (a buried limitation, a deep result) that the
   abstract doesn't state — so those claims read as "partial/no" to the abstract-only checker even
   when correct. The faithfulness drop is partly the instrument penalizing exactly the depth we
   added.
2. **Displacement**: critique text competes for the composer's attention/space, trading a little
   breadth-of-grounding (fewer landmark ids cited) for depth on a few papers.

## Ablation finding & caveat
Net: at these settings, full-PDF critique is **not a clear win** as measured — a genuine negative
result. It should be kept modest (low `critique_k`) and re-evaluated with a *full-text* faithfulness
checker (not abstract-only) before claiming a depth benefit. This is the cleanest illustration in the
suite that an intuitively-good lever must be *measured*, not assumed.
