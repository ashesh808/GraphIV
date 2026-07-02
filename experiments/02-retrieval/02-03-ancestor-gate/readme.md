# 02-03-ancestor-gate

**What:** a cosine floor on the most-cited-ancestor injection — the mechanism through which `02-02`'s
~22% off-topic noise enters. Sensitivity-swept 0.25–0.45 (step 0.05) on BOTH precision (27 topics)
and gold recall (3 topics).

**Conclusion:** **recall sits on a flat 0.25–0.35 plateau** (0.808 / spine 1.0, identical) while
precision rises monotonically — so **0.35 is the max-precision edge of the plateau**, not a tuned
peak. The cliff starts at 0.40 and 0.45 collapses recall (0.522): those floors cut genuine
low-cosine foundational papers. **Shipped:** `augment_with_ancestors(min_cosine=0.35)` is now the
production default in `pipeline.py` and the harness recipe.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (reuses `02-02`'s judge cache).
