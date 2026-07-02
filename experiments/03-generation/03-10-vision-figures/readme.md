# 03-10-vision-figures

**What:** toggle the Gemma-4-26B-Vision figure gallery on/off over the 8 deep-panel topics — does
adding architecture diagrams / result plots (with a caption-faithfulness tripwire) improve the review?

**Conclusion:** **enrichment, not a text lever — ship as an option.** Figures-on adds ~13 figures at
0.91 caption-faithfulness and ~900 words, but the textual 4-axis judge is unchanged (it reads text,
not images). The value is verified visual grounding the text judge can't see; a clean additive
feature at the cost of a vision pass.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
