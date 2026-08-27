# 03-01-attribution

**What:** of the sentences in a report that cite a paper, how many does that paper actually
support. Ten deep reports over five questions, each written with and without the citation digest. Each claim
is checked against the cited paper's own text, retrieving the passages that share the most words
with the claim rather than reading the head of the document. A sentence citing several papers
passes when any one of them supports it.

**Conclusion:** **about seven in ten cited sentences are directly supported.** Gemma scores
0.714 and Qwen 0.744 over the same 818 sentences, and they agree on 90.6% of individual
sentences (kappa 0.762), so the number is a property of the reports and not of the judge.

Full write-up: `results/metrics.md`. Run: `uv run python run.py`.

## Why two judges

Gemma-4-26B wrote these reports, so scoring them with Gemma alone would be self-grading.
Qwen is a different family and scored the same sentences. Gemma was the stricter of the two on
its own output, which is the opposite of the bias that was worth guarding against.

## What "supported" means

The judge answers yes, partial or no. Only yes counts. Counting partial as a pass moves Gemma
from 0.714 to 0.831 and Qwen from 0.744 to 0.779, which flips which judge looks stricter, and that looser reading is reported in `results/metrics.json` but is not
the headline.
