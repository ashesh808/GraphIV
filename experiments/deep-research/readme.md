# deep-research (flagship)

**The deployed pipeline, dogfooded end-to-end** — the holistic before/after, not a single-lever
ablation. `before-2023` (old single-pass default) vs `after-deep` (full deep pipeline: judge-loop,
PPR, recency, frontier-pull, critique, vision figures) over the deep panel. The long reviews + figure
galleries under `results/runs/` (sample in `results/showcase/`) are the primary artifact.

**The jump (deep panel, n=8):** after-deep wins pairwise **8/0/0 on grounding** and **5/2/1 overall**
(win/tie/loss) — 9.0 2026-papers/topic (vs 0), 2.4× frontier coverage, 5× length, 1.5× grounded
citations, 13 verified figures at 0.92 caption-faithfulness. Gold recall dips (0.92→0.81, a
deliberate lineage→frontier reallocation). **This is what gets deployed.**

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
