# deep-research (flagship)

**The deployed pipeline, dogfooded end-to-end** — the holistic before/after, not a single-lever
ablation. `before-2023` (old single-pass default) vs `after-deep` (full deep pipeline: judge-loop,
PPR, recency, frontier-pull, critique, vision figures) over the deep panel. The long reviews + figure
galleries under `results/runs/` (sample in `results/showcase/`) are the primary artifact.

**The jump (deep panel, n=8):** judged on the FULL reports (untruncated, order-debiased), after-deep
wins pairwise **8/0/0 on overall and grounding** — a verdict confirmed unanimously by two
disjoint-family judges (GLM-4.7-Flash, GPT-OSS-20B): zero baseline wins in 96 axis-verdicts
([`results/multi_judge.md`](results/multi_judge.md); sign test p≈0.008 per judge). Objectively: 9.0
2026-papers/topic (vs 0), 2.4× frontier coverage, 5× length, 1.5× grounded citations, 13 verified
figures at 0.92 caption-faithfulness. Gold recall dips (0.92→0.81, a deliberate lineage→frontier
reallocation). An earlier 16k-char judge cap saw only half of each deep report and reported a softer
5/2/1. **This is what gets deployed.**

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
