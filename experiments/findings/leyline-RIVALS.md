# What the system finds when it is asked about its own area

Four questions, effort 5, asked 2026-09-19, capped at that date.
Each took 25 to 30 seconds.
The prior list was hand-read on 2026-09-02 and is in `scratchpad/report-gen-lit/`, which held SurGE,
SciReviewGen, LitLLMs, SurveyForge, PaSa, LitSearch and RollingEval.
Every system below is new against that list.

## The eight that overlap what we claim

| paper | what it is | scale | where it touches us |
| --- | --- | --- | --- |
| `2606.22342` SciTraj | typed citation corpus, six relation types, each edge paired with the claim sentence, NLI-verified, chained into multi-step typed trajectories | 32,559 papers, 573,126 edges | the same premise, typed edges carry the story. It is a corpus built by chaining typed edges, not a walk, so Leyline is not in it |
| `2604.28158` Intern-Atlas | methodological evolution graph, method-level entities, lineage between methods, the bottleneck that drove each transition | 1,030,314 papers | our lineage, one level of abstraction above it, and pitched at AI research agents |
| `2605.15011` Scientific Contribution Graph | contributions linked to prerequisites, plus a prerequisite prediction task scored by temporally filtered backtesting at 0.48 MAP | 655k papers, 6M contributions, 36M edges | our time-travel evaluation, with a predictive number we do not have |
| `2609.00313` MUSES | prospective intellectual-roots retrieval, author-confirmed root labels, rhetorical layer over citation text at LLM-judge kappa 0.896 | 2.33M papers, ~140K test instances per tier | the answer key we wrote down as impossible, built |
| `2608.27394` RATIO | retrieval benchmark typed by ideation move: Address, Broaden, Specify, from full text by discourse-marker distant supervision | millions of full-text CS papers | typed retrieval as a benchmark rather than as a ranking signal |
| `2604.17680` MasterSet | must-cite citation recommendation benchmark, direct baselines and core dependencies rather than broad relevance | 150,000 papers, 15 venues | ConsensusMatch, annotated by hand instead of mined |
| `2510.07733` SurveyG | survey generation over a hierarchical citation graph, edges are citation plus semantic relatedness | not stated in the abstract | the structural half of report generation |
| `2608.16602` Declining modularity | co-citation modularity falling as a research area emerges, with a statistical robustness test | 3 areas | a frontier signal with a validation we do not have |

## What is left that is ours

| | still only here |
| --- | --- |
| labeled edge count | 73.0M intent-labeled edges over 3.13M papers, against SciTraj's 573K over 32.5K and the Contribution Graph's 36M over 655K |
| a query-time system | seven of the eight are corpora, benchmarks or analyses, not something you ask a question and get an answer from |
| the whole chain in one call | refine, retrieve, rank, lineage, successors, author-stated limits, in 27 seconds on one consumer GPU |
| a paper with zero citations can rank | by the stance edges it makes, which no benchmark above rewards |
| self hosted and reproducible end to end | from a public snapshot, no API key anywhere |

## What they have that we do not

| gap | who has it | what ours is |
| --- | --- | --- |
| edge labels checked against a human set | MUSES, LLM judge kappa 0.896 against human | 985 rows in `data/citation_labeler/ground_truth.csv`, which is the set the student is scored on |
| a predictive task with a number | Contribution Graph, 0.48 MAP on temporally filtered backtesting | four recall benchmarks, none predictive |
| method-level entities | Intern-Atlas | paper-level nodes only |
| a benchmark other people can run | MasterSet, MUSES, RATIO, SurGE | four benchmarks that only rebuild inside this repo |

## Where the answers are

```
answers/survey_generation_5.md
answers/citation_retrieval_5.md
answers/frontier_detection_5.md
answers/intent_edges_use_5.md
cases/rivals.toml
```

`intent_edges_use` drifted into e-commerce generative retrieval and is the weakest of the four,
which is the same failure that question shows on the benchmark at 0.05 to 0.15 by the judge.
