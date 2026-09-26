# 03-04-source-coverage

**What:** how much of a report is sourced at all. Every sentence is either carrying a citation
or not, counted by regex over the same five reports. No model is involved, so there is nothing
for two judges to disagree about.

**Conclusion:** **818 of 1372 sentences carry a citation, 60%.** The remaining 554 are mostly
section openings, syntheses of the paragraph below them, and figure descriptions.

Full write-up: `results/metrics.md`. Run: `uv run python run.py`.

## Why this is a count and not a judgement

The natural question is how many of the 284 uncited sentences invent something. That was tried
twice and abandoned. A five-way label scheme (filler, caption, restatement, conclusion, new
fact) put Gemma at 37 new facts and Qwen at 67. Collapsing it to one yes-or-no question made it
worse: 12 against 91, with a kappa of 0.003, which is chance agreement.

The reason is that the question has no fixed answer. "The field moved from X to Y" is a
restatement under a generous reading and a new claim under a strict one, and two models pick
different strictness without either being wrong. A cited sentence has a document to check
against; an uncited one has only the reader's threshold.

So the measurable version is the count above. Splitting the 284 needs human labels, not a
better prompt.
