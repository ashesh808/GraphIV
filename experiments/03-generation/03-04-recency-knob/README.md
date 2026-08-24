# 03-04-recency-knob

**What:** sweep the topic-adaptive `recency` dial (0.0–0.8) over the 27-topic battery — how it trades
lineage depth for frontier coverage.

**Conclusion:** **a control surface, not a winner.** Frontier landmarks climb monotonically (3.7 →
30.8) at roughly constant grounding — the knob does exactly what it should, and there's no universal
optimum (foundations-questions want low, latest-questions want high). Correctly exposed as a per-query
knob with a mid default.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
