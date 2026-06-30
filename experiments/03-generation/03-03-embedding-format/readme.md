# 03-03-embedding-format

**What:** which query-embedding shape retrieves best, judged end-to-end — `sym`/`asym` ×
`hyde`/`raw`, 3 gold topics.

**Conclusion:** **ship `asym_raw` (committed).** The nomic asymmetric `search_query`/`search_document`
encoding on the raw question ties for best recall (0.81 / spine 1.0) at no extra cost; HyDE only helps
the symmetric space and is redundant (and slower) on the asymmetric one. `sym_raw` is the clear loser.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
