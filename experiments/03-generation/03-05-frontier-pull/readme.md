# 03-05-frontier-pull

**What:** toggle the leaf-independent, year-filtered `frontier_pull` on/off over the 27-topic battery
— the corpus-delta recovery path.

**Conclusion:** **ship it on — it's a correctness fix.** The topic tree predates the 2026 delta and
has no 2026 leaves, so without the pull **zero** 2026 papers ever surface (1.9/topic with it on), at
no cost to frontier count or grounding. It fills a structural blind spot, not a quality knob.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
