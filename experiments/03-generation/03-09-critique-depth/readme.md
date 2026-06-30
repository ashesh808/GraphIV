# 03-09-critique-depth

**What:** vary `critique_k ∈ {0,4,8}` — per-paper full-PDF critiques in the deep loop, 27 topics. Does
reading more PDFs per round help?

**Conclusion:** **a documented near-null.** The first few critiques nudge gold recall (0.85→0.92 at
k4), but k8 adds nothing and faithfulness slips (0.95→0.90). Pairwise k8-vs-k0 is a weak 0.63 with no
objective gain. Keep `critique_k` ≈ 4; depth beyond that is cost + a faithfulness risk, not quality —
the deep loop's win is the expand rounds, not deeper critiques.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
