# landmark-selection

**What:** how to pick the ~40-paper subgraph the review is built from — `fixed40` vs `gate40` (0.35
cosine) vs `llm40` / `llm_dyn` (LLM-relevance filter), disentangling filter-type from count, on the
Exp-1-validated metric.

**Conclusion:** **the win is the filter, not the count.** `llm40` (relevance-filter at the same 40
papers) wins — perfect precision, full recall, best coverage, beats fixed-40 5/8 — at zero size
increase. Going bigger (`llm_dyn`, 60) adds nothing. Ship the cheap 0.35 gate at minimum; LLM filter
for precision-max. **Keep the list small, filter for relevance, don't expand.**

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [topic ...]`. Reuses the consolidated `_harness`
helpers (`retrieve_subgraph` / `adjacency_digest` / `role_judge`).
