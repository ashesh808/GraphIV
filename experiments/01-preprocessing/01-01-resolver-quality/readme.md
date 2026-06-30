# 01 — resolver quality

**What:** characterizes the phase-3 5-layer citation resolver (`link → text → doi → jref →
title-exact → title-fuzzy`) by reading `citation.method` from Postgres — what each layer resolves,
by field and era. Pure SQL, no LLM.

**Conclusion:** **40.18 %** of 177M citation occurrences resolve to an arXiv id; the exact layers
carry ~80 % and the fuzzy tail is bounded at ~11 %, so the cascade gains recall without leaning on
the riskiest matcher.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [--no-cache]`.
