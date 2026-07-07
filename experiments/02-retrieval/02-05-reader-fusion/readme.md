# 02-05-reader-fusion

**What:** the measure-gate for the shipped `--include-fuse` lever. Every landmark candidate is
graded by the production reader (`reader_grade`: 6-class role — foundational/core/frontier/
adjacent/survey/unrelated — + relevance -2..2, cached by question-hash); ranking then runs on
`cosine × (rel+2)/4` with -2 papers excluded (they stay in the pool as graph connectors).
Variants: `baseline` (cosine-only), `fuse` (production formula), `fuse_mild` (norm in [0.5,1],
no self-exclusion). Scored on gold recall (3 topics, grader-independent — THE gate) +
relevance_rate/composition (27 topics; same-grader caveat: precision gains are partly
by-construction, so the ship decision hangs on recall not regressing).

**Conclusion:** **Pareto win — SHIPPED as the `fuse: true` default.** Gold recall is IDENTICAL
across all variants (landmark 0.808, spine 1.0 — fusion loses nothing the review must cover),
while `fuse` removes every unrelated landmark (5.7% → 0%, relevance 0.945 → 1.0; same-grader
caveat applies to the precision numbers, not to recall) and shifts the freed slots to
core (0.270 → 0.307) and frontier (0.224 → 0.257). `fuse_mild` sits strictly between — no
reason to prefer it. Baseline relevance is already 0.945 (vs 02-02's historical 0.78) because
the 0.35 ancestor floor shipped in between; the residual noise is exactly what fusion removes.
Noisiest topic: `transformer_progsynth` (19/63 candidates at −2 — a thin-corpus query where
exclusion matters most).

Run: `uv run python experiments/02-retrieval/02-05-reader-fusion/run.py` (grades are cached in
`data/metadata/grade_cache.db`, shared with production runs of the same query strings).
