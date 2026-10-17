# eval

The four benchmarks that score a recipe, and the code they share.
Nothing here runs on its own, and we run the benchmarks with `scripts/evaluate_retrieval/`.

```
match.py            what every benchmark shares: the question it asks, the score and the row it writes
cases.py            mines the cases out of the store, the same ones for the same seed
query_writer.py     writes the one question a set of reviews would have been written to answer
survey_match.py     SurveyMatch: the papers one review cited
frontier_match.py   FrontierMatch: what the next review on a topic added
consensus_match.py  ConsensusMatch: the papers every review of a topic cites
precision_match.py  PrecisionMatch: how much of an answer is about the topic at all
report.py           the run directory a benchmark leaves, and the figure comparing its recipes
```

Each case is capped at its review's date, and the cap goes into the pipeline rather than being applied afterward.
A model writes each case's question, and nothing else in a benchmark calls one.
What each benchmark asks and how it scores is in [`docs/retrieval.md`](../../docs/retrieval.md#evaluation).
