# 03-09-critique-depth

**What:** vary `critique_k ∈ {0,4,8}` — per-paper full-PDF critiques in the deep loop, 8 deep-panel
topics. Does reading more PDFs per round help?

**Conclusion:** **a documented null.** The first few critiques nudge gold recall (0.88→0.92 at k4)
and grounded citations (45.9→47.8), but k8 gives it all back (recall 0.88, grounded 43.5) and
faithfulness slips monotonically (0.99→0.95→0.94). Pairwise k8-vs-k0 is 2/2/4 overall (mostly ties)
with no objective gain. Keep `critique_k` = 4; depth beyond that is cost + a faithfulness risk, not
quality — the deep loop's win is the expand rounds (03-08), not deeper critiques.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
