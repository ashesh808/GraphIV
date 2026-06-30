# 03-08-judge-loop

**What:** vary the judge-driven gap-expansion round cap (`max_rounds ∈ {1,2,4,6}`) on the deep path,
27 topics — is test-time compute worth it for review generation?

**Conclusion:** **yes — ship deep with cap ≈ 4.** More rounds nearly double landmarks (77→151) and
frontier coverage, and gold recall peaks at 0.96 (rounds-4). The compressed absolute judge hides it,
but the **pairwise is decisive: rounds-6 beats rounds-1 0.78 overall.** The thinking judge self-stops
(~2.8 rounds run even at cap 6), so the cap is just a ceiling.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
