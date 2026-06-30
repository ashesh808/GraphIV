# 02-02-relevance-judge

**What:** the PRECISION + COMPOSITION recall can't measure — a gold-free Gemma-4-26B role label
(foundational/core/frontier/peripheral/unrelated) on every committed landmark, over all 27 topics.

**Conclusion:** **~78% on-topic, 89% of topics span their full lineage** — but **~22% is off-topic
noise that PPR can't see** (unrelated papers carry in-degree 5.4, as high as core: famous cross-field
hubs riding in on citation fame). That noise is the target of `02-03-ancestor-gate`. Labels are
corpus-stable and cached in `cache/judge_cache.db` (shared with `02-03`).

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (`--no-cache` re-judges).
