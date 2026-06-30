# 02-01-subgraph-retrieval

**What:** the committed subgraph-retrieval recipe (hybrid pool → ancestor augment → induce → PPR) in
isolation — does it recover a field's canonical landmarks as a bounded, connected, on-topic citation
subgraph? Retrieval level only (no LLM/compose/judge), vs PCST and similarity-aware-BFS selectors.

**Conclusion:** **the defendable number** — `induce`/PPR recovers **0.742** of canonical landmarks
and **0.917** of the foundational spine against a **0.85** pool ceiling (≈87% of reachable kept). It
dominates every recall axis; PCST wins only connectivity (a downstream presentation concern). Keep
the committed recipe.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (add `uv run --with pcst_fast` for the PCST baseline).
