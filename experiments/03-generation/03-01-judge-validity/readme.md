# judge-validity

**What:** validates the Gemma-4-26B LLM judge (the measurement instrument) against ground truth —
known-fact accuracy, degradation detection per axis, and position/verbosity bias.

**Conclusion:** judge is sound — **100%** on known facts, catches coverage + grounding degradations,
**no position/verbosity bias**; **lineage is the weak axis**. So downstream: trust grounding/coverage
+ large effects, asterisk lineage + tiny margins.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
