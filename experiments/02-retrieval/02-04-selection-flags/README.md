# 02-04-selection-flags

**What:** an ablation on how to pick the landmark set, scored at the **per-paper** level (−2..+2 on
salient full text, 27 topics) so the count tension is visible: `fixed50` vs `gate50` (0.35 cosine) vs
`llm50` (LLM filter, same count) vs `llm_dyn` (filter + bigger).

**Conclusion:** **the count doesn't matter — cosine-gate and LLM-filter are independent on/off
flags.** Filtering lifts both sum (+42%) and mean (+40%); going bigger (`llm_dyn`) lifts only `sum`
(clean relevant mass) while `mean` saturates at ~0.88 — same place the compose-judge says the review
saturates. Ship the cheap 0.35 gate (free), add the LLM filter for precision-max; keep the cap small.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [topic ...]` (`--no-cache` rescores).
