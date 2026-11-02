# docs

What GraphIV's methods are, and how to build or restore it.
The code's own structure is in each package README, and measurements live in `research/experiments/`.

```
retrieval.md     BoundedField, the retriever and reranker: its pool, its score, its tuning and its benchmarks
leyline.md       LeyLine, the miner: magnets, the Monte Carlo walks, lineages and successors
benchmarks.md    SurveyMatch, FrontierMatch and ConsensusMatch: how a case is built, the versions and the splits
supplement.md    the Topic Queries behind LeyLine's Unseen Newcomer evaluation
preprocess.md    the build: what to supply, what to run in what order, how to check it landed
restore.md       skip the build, restore the published dump and serve from it
storage.md       PostgreSQL and immutable SQLite/FAISS corpora, Azure snapshots, and durable reports
published-corpus-validation.md  published release rollout, measured checks, and outstanding real acceptance
```
