# 02-03-ancestor-gate

**What:** a cosine floor on the most-cited-ancestor injection — the mechanism through which `02-02`'s
~22% off-topic noise enters. Swept 0.0 / 0.35 / 0.45 (+category), scored on BOTH precision (27
topics) and gold recall (3 topics).

**Conclusion:** **a gentle 0.35 floor is a Pareto win** — precision +5.6 pts AND gold recall up
(0.742→0.808, spine →1.0): dropping off-topic hubs frees PPR slots for on-topic papers. 0.45 is the
real tradeoff (recall collapses); the category gate adds nothing. **Ship `min_cosine ≈ 0.35` on
`augment_with_ancestors`** — a measured, unshipped production win.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (reuses `02-02`'s judge cache).
