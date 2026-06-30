# 03-10-vision-figures

**What:** toggle the Gemma-4-26B-Vision figure gallery on/off over 27 topics — does adding
architecture diagrams / result plots (with a caption-faithfulness tripwire) improve the review?

**Conclusion:** **enrichment, not a text lever — ship as an option.** Figures-on adds ~12 figures at
0.93 caption-faithfulness and ~1000 words, but the textual 4-axis judge is unchanged (it reads text,
not images). The value is verified visual grounding the text judge can't see; a clean additive
feature at the cost of a vision pass.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
