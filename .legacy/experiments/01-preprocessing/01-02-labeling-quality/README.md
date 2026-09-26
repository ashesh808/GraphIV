# 02 — labeling quality

**What:** measures phase-3 citation-edge labeling — the Gemma teacher prompt's 6-round evolution and
the distilled DistilBERT student's held-out PRF for both heads (intent 6-way, polarity 3-way). Reads
frozen training artifacts; no LLM.

**Conclusion:** polarity near-solved (acc **0.95**); intent strong overall (acc **0.84**, macro-F1
**0.72**) but the rare relational intents lag (`critiques` 0.58) — precisely the edges phase-6's
tensions surfacing relies on, and what the human-gold set must validate.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`. (`src/gold_tool.py` = the Phase-C human-gold tool.)
