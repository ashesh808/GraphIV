# 03-11-hub-suppression

**What:** keep generic globally-cited hubs (Attention 27/27 reports, BERT, GPT-3, Adam) from dominating
niche reviews — a specificity problem, no blocklist. A data-derived signal sweep (lift / intent
background-ratio / pop_bg / pr_ratio) over 27 topics, scored on gold-recall (tripwire) + an independent
topic-conditioned specific/generic LLM oracle.

**Conclusion:** **no purely-structural silver bullet** — a hub genuinely *used* in a niche (Attention in
theorem-proving) can't be removed without recall cost, because "generic for this topic" is partly a
*narrative* call. So the **shipped fix is a compose guard** (`compose_report` + `long_compose`),
A/B-validated: on RL-for-theorem-proving it removes the "Rise of Transformers" section and drops
Attention/BERT/GPT-3/Adam from 3/1/3/1 to **0/0/0/0** while preserving the ATP-specific coverage; zero
generic-hub mentions on 3 further niche topics. The recall-safe `pop_bg` retrieval lever stays available
for generic-*method* residue.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (regenerates table+figure from the committed
`results/{structural,oracle}.json`); reproduce those with `code/hub_sweep.py` then `code/hub_oracle.py`
(GPU + LLM heavy).
