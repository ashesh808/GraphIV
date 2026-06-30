# deep-research (flagship)

**The deployed pipeline, dogfooded end-to-end** — the holistic before/after, not a single-lever
ablation. `before-2023` (old single-pass default) vs `after-deep` (full deep pipeline: judge-loop,
PPR, recency, frontier-pull, critique, vision figures) over the deep panel. The long reviews + figure
galleries under `results/runs/` (sample in `results/showcase/`) are the primary artifact.

**The jump:** after-deep is preferred **23/4/0 overall (1.0 on grounding)** — 3.3 2026-papers/topic
(vs 0), 3× frontier coverage, 5× length, 2× grounded citations, 12 verified figures. Gold recall dips
slightly (0.96→0.85, a deliberate lineage→frontier reallocation the judge strongly endorses). **This
is what gets deployed.**

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
