# 03-08-judge-loop

**What:** vary the judge-driven gap-expansion round cap (`max_rounds ∈ {1,2,4,6}`) on the deep path,
8 deep-panel topics — is test-time compute worth it for review generation?

**Conclusion:** **yes — test-time compute works.** More rounds more than double landmarks (80→170)
and frontier coverage (37→74), and gold recall climbs 0.81→0.96. The compressed absolute judge hides
it, but the **pairwise is decisive: rounds-6 beats rounds-1 6/0/2 (0.75 overall)**, sweeping coverage
and lineage with zero losses on any axis. The thinking judge self-stops (~3.4 rounds run even at cap
6, ~2.4 at cap 4), so the cap is only a ceiling — shipped as `effort 4` (cap 4) / `effort 5` (cap 6).

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
