# Leyline as the lineage stage, the model refining the question, and full text at the top of the dial

## What was asked

| ask | what was built |
| --- | --- |
| let the model break down and refine the question as it once did | `refine.py`, one call that names the area, its method words, 3 to 5 sub-queries, the exclusions and the mode |
| effort should read the full text when it is needed | `fulltext.py`, which opens the html already on disk and reads only the sections where authors state their own limits |
| bring Leyline back, with a new definition of a magnet node | `magnet.py`, where a magnet is a paper the field takes a position on rather than a paper the reader graded 2 |

## Configuration

| item | value |
| --- | --- |
| corpus | 3,128,573 papers, 73.0M resolved citations, all labeled by intent |
| retriever | `survey.toml`, `cos .75 rec .75 anc 4 fro .25 cocite .5 hub .5`, seed 5000 |
| model | Gemma-4-26B-Batched, `reasoning_effort: "none"`, 8 in parallel, every completion cached |
| cases, hard set | `scratchpad/selfstudy/questions.toml`, 14 broad methodological questions |
| cases, easy set | `scratchpad/frontier-system/personas.toml`, 6 researchers with long briefs |
| date cap | 2025-03-01 for both scored sets |
| answer size | top 20 |

## The three measures, and why there are three

| measure | what it is | what it cannot see |
| --- | --- | --- |
| on topic, tree | share of the top 20 the topic tree puts in the level-1 nodes the baseline pool voted for | the tree at level 1 is coarse, so a correct answer in a neighboring node counts as a miss |
| on topic, judge | share of the top 20 the model says a review of that question would cite, one paper per call | the model is the same one the reader stage uses |
| in the review key | share of the top 20 that reviews written in the following 18 months went on to cite | a paper is only in it if it was already being cited, so it cannot reward a cold breakout |

The area a system is scored against is voted by the **baseline** pool, so changing the retrieval
cannot move the target. Membership is tested against the area's tree nodes and not against the
baseline pool, so a paper the baseline never retrieved can still be counted on topic.

The topic tree is never used as a filter inside any system measured here, since it is the metric.

## The hard set, 14 broad methodological questions

| system | on topic, tree | in the review key | on topic, judge |
| --- | --- | --- | --- |
| baseline | 0.600 | 0.064 | 0.314 |
| brief only, reader | 0.686 | 0.100 | 0.486 |
| sub-queries, no gate | 0.593 | 0.064 | 0.332 |
| gate 2 | 0.696 | 0.061 | 0.400 |
| gate 4 | 0.732 | 0.046 | 0.471 |
| gate 8 | 0.743 | 0.050 | 0.507 |
| gate 4, reader | 0.743 | 0.068 | 0.575 |
| mix | 0.657 | 0.071 | 0.421 |
| mix, reader | 0.682 | 0.121 | 0.482 |


Per question, on topic by the judge.


| question | baseline | brief only, reader | sub-queries, no gate | gate 2 | gate 4 | gate 8 | gate 4, reader | mix | mix, reader |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cold_start | 1.00 | 0.95 | 0.80 | 0.70 | 0.85 | 0.90 | 0.85 | 0.95 | 0.95 |
| connectivity_vs_relevance | 0.10 | 0.30 | 0.00 | 0.00 | 0.00 | 0.00 | 0.05 | 0.10 | 0.25 |
| citation_key_bias | 0.55 | 0.40 | 0.60 | 0.60 | 0.60 | 0.75 | 0.55 | 0.70 | 0.35 |
| query_breadth | 0.15 | 0.35 | 0.15 | 0.35 | 0.35 | 0.30 | 0.40 | 0.35 | 0.35 |
| negation | 0.00 | 0.10 | 0.10 | 0.10 | 0.20 | 0.25 | 0.40 | 0.05 | 0.25 |
| intent_edges | 0.00 | 0.10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.05 | 0.00 | 0.15 |
| topic_from_citations | 0.25 | 0.30 | 0.20 | 0.35 | 0.60 | 0.85 | 1.00 | 0.40 | 0.50 |
| llm_rerank_cost | 0.35 | 0.80 | 0.45 | 0.65 | 0.65 | 0.70 | 0.95 | 0.55 | 0.65 |
| human_ceiling | 0.15 | 0.35 | 0.40 | 0.35 | 0.55 | 0.35 | 0.50 | 0.35 | 0.30 |
| stale_benchmarks | 0.45 | 0.85 | 0.60 | 0.85 | 0.90 | 1.00 | 1.00 | 0.75 | 0.85 |
| grounded_generation | 0.60 | 1.00 | 0.75 | 0.90 | 1.00 | 1.00 | 1.00 | 0.80 | 1.00 |
| survey_detection | 0.30 | 0.65 | 0.15 | 0.25 | 0.30 | 0.30 | 0.45 | 0.35 | 0.45 |
| hub_suppression | 0.10 | 0.10 | 0.05 | 0.20 | 0.30 | 0.45 | 0.45 | 0.20 | 0.15 |
| effort_scaling | 0.40 | 0.55 | 0.40 | 0.30 | 0.30 | 0.25 | 0.40 | 0.35 | 0.55 |

## The easy set, 6 researchers with long briefs

| system | on topic, tree | in the review key | on topic, judge |
| --- | --- | --- | --- |
| baseline | 0.900 | 0.683 | 0.758 |
| brief only, reader | 0.942 | 0.675 | 0.933 |
| sub-queries, no gate | 0.917 | 0.725 | 0.792 |
| gate 2 | 0.933 | 0.700 | 0.867 |
| gate 4 | 0.958 | 0.675 | 0.892 |
| gate 8 | 0.933 | 0.608 | 0.858 |
| gate 4, reader | 0.967 | 0.700 | 0.975 |
| mix | 0.925 | 0.733 | 0.800 |
| mix, reader | 0.925 | 0.633 | 0.925 |


## What a magnet is now

```
stance(p)  = sum over in-pool citers c of W[intent(c -> p)] * cos(c)
total(p)   = sum over in-pool citers c of cos(c)
magnet(p)  = stance(p) * stance(p)/total(p) * cos(p, named area)
```

| intent | W | edges in the corpus |
| --- | --- | --- |
| extends | 1.0 | 2.5M |
| critiques | 1.0 | 2.7M |
| compares | 0.8 | 5.2M |
| uses | 0.4 | 11.6M |
| motivates | 0.15 | 0.66M |
| background | 0.0 | 51.1M |

The old magnet was any paper the reader graded 2, which makes a famous paper a magnet in every
area it is cited in. The three factors each remove one failure of that:

| factor | what it removes |
| --- | --- |
| stance mass | a paper nobody argues with, however often it is named |
| stance share | a paper cited as background by everything, which is the generic hub |
| area cosine | a paper argued about for a reason other than this question |

### mechinterp, the ten most cited in the induced subgraph against the new weight

| in-head citers | new weight | title |
| --- | --- | --- |
| 513 | 1.000 | Interpretability in the Wild: a Circuit for Indirect Object Identification |
| 343 | 0.942 | Scaling and evaluating sparse autoencoders |
| 327 | 0.366 | Sparse Autoencoders Find Highly Interpretable Features in Language Models |
| 302 | 0.425 | Toy Models of Superposition |
| 277 | 0.221 | Locating and Editing Factual Associations in GPT |
| 244 | 0.704 | Scaling Monosemanticity |
| 207 | 0.485 | Sparse Feature Circuits |
| 196 | 0.160 | In-context Learning and Induction Heads |
| 153 | 0.239 | Towards Automated Circuit Discovery |
| 143 | 0.106 | Language Models are Few-Shot Learners |

### tabular, the same comparison

| in-head citers | new weight | title |
| --- | --- | --- |
| 374 | 1.000 | Why do tree-based models still outperform deep learning on tabular data? |
| 276 | 0.613 | XGBoost: A Scalable Tree Boosting System |
| 271 | 0.135 | Language Models are Few-Shot Learners |
| 238 | 0.322 | Attention Is All You Need |
| 232 | 0.381 | SAINT |
| 226 | 0.157 | BERT |
| 222 | 0.259 | TabNet |
| 208 | 0.598 | When Do Neural Nets Outperform Boosted Trees on Tabular Data? |

`Attention Is All You Need` and `Language Models are Few-Shot Learners` are the two hubs the old
definition could not remove. Both are now below every paper that is actually about the question.

## What a line looks like

One line out of the tabular answer at effort 5, magnets in bold.

| date | paper |
| --- | --- |
| 2016-03-09 | **XGBoost: A Scalable Tree Boosting System** |
| 2017-06-28 | **CatBoost: unbiased boosting with categorical features** |
| 2022-03-10 | **On Embeddings for Numerical Features in Tabular Deep Learning** |
| 2022-07-05 | **TabPFN: A Transformer That Solves Small Tabular Classification Problems** |
| 2022-07-18 | **Why do tree-based models still outperform deep learning on tabular data?** |
| 2022-11-28 | **What learning algorithm is in-context learning?** |
| 2023-05-04 | **When Do Neural Nets Outperform Boosted Trees on Tabular Data?** |
| 2023-05-18 | **Statistical Foundations of Prior-Data Fitted Networks** |
| 2025-02-08 | **TabICL: A Tabular Foundation Model for In-Context Learning on Large Data** |
| 2025-06-05 | TabFlex: Scaling Tabular Learning to Millions with Linear Attention |
| 2026-05-13 | **TabPFN-3: Technical Report** |

## The effort dial

| level | what it adds | stages that run |
| --- | --- | --- |
| 0 | nothing, the shipped graph score | retrieve |
| 1 | the model names the area, which becomes the gate | refine, retrieve, anchor |
| 2 | the sub-queries the model wrote, one pool each | + 4 more pools |
| 3 | the reader on the top 100, dropping what it calls unrelated | + read |
| 4 | Leyline over the top 300, and the successors with a stance | + lineage, successors |
| 5 | the full text of 8 papers, read for their own stated limits | + full text |

Measured per stage, cold cache, on a question never asked before.

| stage | seconds |
| --- | --- |
| refine | 1.78 |
| retrieve, 1 pool | 1.49 |
| retrieve, 5 pools | 6.45 |
| anchor cosines over the pool | 0.61 |
| reader, top 100 | 11.58 |
| lineage, 300 nodes and about 9,000 edges | 2.87 |
| successors | 0.02 |
| full text, 8 papers | 3.74 |

| level | cold | warm |
| --- | --- | --- |
| 0 | 1.5 | 0.6 |
| 1 | 3.9 | 1.4 |
| 2 | 8.8 | 3.3 |
| 3 | 20.4 | 14.8, the reader was still cold |
| 4 | 23.3 | 5.8 |
| 5 | 27.0 | 9.3 |

Warm means every completion was already in the cache, which is what a second question in the same
area costs. Old graphiv was 431 seconds for one answer, of which 8.7 was retrieval.

### What each rung buys, 14 hard questions, by `levels.py`

| level | on topic, tree | on topic, judge | in the review key | seconds, warm |
| --- | --- | --- | --- | --- |
| 0 | 0.600 | 0.314 | 0.064 | 0.4 |
| 1 | 0.700 | 0.411 | 0.075 | 1.2 |
| 2 | 0.696 | 0.400 | 0.061 | 4.8 |
| 3 | 0.711 | 0.571 | 0.079 | 3.2 |

Level 2 is the sub-queries, and it is a loss on all three measures at four times the cost of
level 1. Levels 4 and 5 leave the ranking untouched and add the lineage, the successors and the
limitations, so they are not in this table.

## The dial, renumbered

The floor is a document, not a list. A ranked list is a stage.

| level | name | budget | what it adds |
| --- | --- | --- | --- |
| 0 | the story | about half a minute | the state, the lines, the successors, the limits of 8 papers |
| 1 | read the papers | about ten minutes | a schema the model chose, filled from 120 papers, plus what others measured about 40 |
| 2 | read everything | about half an hour | the same over 300 papers and 100 measured |

Measured on one question never asked before, `answers/rag_*.md`.

| level | seconds | papers in the table | independent numbers | citing papers read |
| --- | --- | --- | --- | --- |
| 0 | 22.0 | 0 | 0 | 0 |
| 1 | 217.8 | 94 | 18 | 935 |
| 2 | 339.4 | 212 | 141 | 2,298 |

Both upper levels finish inside their budget, so the caps are set by the rung and not by the clock.

## The two extraction runs

The schema run is the old graphiv shape: the model proposes fields for this question, then fills them per
paper. The measured run is new: the `compares` edges name the papers that benchmarked against a target, and
the target's row is taken out of their results tables.

| | schema run | measured run |
| --- | --- | --- |
| what it gives | method, benchmark, baselines, scaling limit, one row per paper | one number per row, with the paper that reported it |
| where the text comes from | the paper's own method and results sections plus every numeric table | the baseline row of a citing paper's own results table |
| the number is | the paper's own claim | independent of the paper |
| cost | 1.4s a paper at 8 in parallel | 2.2s a target, including reading 24 citing papers |

Both are in the document, as separate sections, since they answer different questions.

### What the schema run fixed against the old version

| | old graphiv | here |
| --- | --- | --- |
| text handed to the model | about 2,900 characters of flattened prose | 6,700 to 10,800 characters of method, results and numeric tables |
| tables shown | none | every table in the paper carrying 6 or more decimal numbers |
| fields answered rather than n/a | not recorded, extraction recall was 0.17 to 0.29 | 4 to 7 of 7 across 8 tabular papers |

The papers where a field comes back n/a are the ones whose results live in figures rather than
tables, which is most of modern machine learning. That is the hole the measured run exists to fill.

### What the measured run rests on

| | |
| --- | --- |
| stance sentences carrying any number at all | 3 of 96 for TabICL, 13 of 472 for the tree-based paper |
| citing papers carrying the target as a numbered baseline row | 16 of 37 for TabICL, 19 of 40 for TabPFN |

So the citation sentence is the wrong place to look for a number and the citing paper's results
table is the right one.

### The reader decides what goes in the table

A magnet is a paper the field argues with, and a famous backbone is argued with everywhere, so the
first comparison table for a tabular question carried BERT, Attention Is All You Need and
Self-Normalizing Neural Networks. Grading the reading set with the six-label reader and keeping
relevance 1 and up removed all three and left 94 papers that are about the question.

## Full text, which every one of these stages rests on

| | |
| --- | --- |
| papers with html landed | 3,128,573 of 3,164,437 |
| papers whose html yielded at least one citation | 2,572,277, which is 82.2% |
| citation occurrences parsed out of that html | 182,559,513 |
| resolved to a paper in the corpus, each carrying its sentence | 73,808,475 |
| papers named across the four effort-5 answers | 378 |
| of those, html on disk | 378, 100% |
| of those, carrying a limitation, discussion or conclusion section | 359, 95.0% |

## What this has that the two systems it is measured against do not

| | old graphiv | Consensus | here |
| --- | --- | --- | --- |
| corpus | this one, 3.13M | 200M+ through Semantic Scholar, OpenAlex, PubMed | this one, 3.13M |
| citation intent labels | none | none | 73.0M edges, six intents |
| a paper with zero citations can rank | no | no | yes, by the stance edges it makes |
| lineage of a field | none | none | Leyline lines, oldest first |
| open problems | written by the model off abstracts | none | quoted from the paper's own limitation section |
| roles for each paper | six labels | none | six labels |
| time to one answer | 431s | seconds | 1.5 to 27s |
| self hosted and reproducible | yes | no | yes |

The shipped frontier answer for the tabular question listed five open problems, none of which
names the paper it came from. The same question at effort 5 lists 22 open problems across 6
papers, each one under the paper and the section title it was read out of.

## Rough edges, measured rather than argued

| edge | what it looks like |
| --- | --- |
| a broad named area lets a generic hub back in | the protein question's lines run through `Adam` and `Denoising Diffusion Probabilistic Models`, because the model named an area wide enough for both |
| the gate loses two questions outright | `connectivity_vs_relevance` goes 0.10 to 0.00 by the judge, since the anchor names a ranking area and the question is about the arithmetic of combining two scores |
| the judge is the same model as the reader | so the reader's gain on the judge column is partly self-agreement, which is why the tree column is reported beside it |
| the tree at level 1 is coarse | `human_ceiling` votes a peer-review node, so an answer about reproducibility of literature searches scores 0.05 on the tree and 0.55 on the judge |
| the review key barely moves | 0.064 to 0.068 on the hard set, where two human reviews of one topic agree at 0.265 |

## Files

| file | what it holds |
| --- | --- |
| `refine.py` | the one call that names the area, the sub-queries and the mode |
| `anchor.py` | cosine against the named area, as a gate and as a floor |
| `magnet.py` | the redefined magnet, the reach walk and the thread mining |
| `fulltext.py` | the limitation sections off the html, and the reading of them |
| `effort.py` | what each level turns on |
| `answer.py`, `write.py`, `ask.py` | one question to one document |
| `bench.py`, `judge.py`, `run.py`, `report.py` | the three measures and the tables above |
| `mine.py`, `diag.py` | what one question returns, printed |
| `answers/` | every document written, one per question per level |
| `results/` | every run, as json and as the log it printed |

## Asking one question at level 2, then asking its open problems back

The question, which had never been asked before, was whether the citation graph is a query-time
signal or something everyone now bakes into the embedding at training time.

| stage | seconds | what it produced |
| --- | --- | --- |
| refine | 28.4 | area named, 5 sub-queries |
| retrieve | 16.9 | 15,132 candidates |
| read | 27.5 | 30 kept |
| lineage | 8.3 | 281 magnets, 6 lines |
| successors | 0.1 | 12 papers with a stance, none cited yet |
| full text | 8.9 | 19 papers opened |
| extract | 298.1 | 168 papers into 6 fields |
| measure | 178.4 | 175 numbers out of 2,299 citing papers |
| total | 566.6 | a 689-line document |

After the two fixes below the same question reads 3,405 citing papers and carries 260
independent numbers in a 773-line document.

### Fill rate of the six fields the model chose for this question

| field | filled | share of 168 |
| --- | --- | --- |
| method_architecture | 165 | 0.98 |
| baseline_comparison | 164 | 0.98 |
| quantitative_metric | 143 | 0.85 |
| computational_efficiency | 88 | 0.52 |
| graph_integration_type | 54 | 0.32 |
| reasoning_capability | 41 | 0.24 |

### The recursion, 44 stated open problems asked back at level 0

Every bullet of the open-problems section was re-asked as its own question, anchored by the title
of the paper that stated it, in 17 minutes for all 44.

| source papers | problems | of the top 10, postdating the source | citing the source | stance edges | with at least one citer |
| --- | --- | --- | --- | --- | --- |
| before 2025 | 18 | 10.00 | 4.06 | 2.17 | 0.83 |
| 2025 and later | 26 | 3.92 | 0.04 | 0.00 | 0.04 |

The split is the cold-start case restated: an open problem stated last quarter has no successors to
return, and the system falls back on cosine inside the named area.

### Two defects the run exposed, both fixed

| defect | cause | fix |
| --- | --- | --- |
| the measured table carried BERT on FUNSD, drone constraints and geographic distance | `find_citers` ordered a target's citers by date, and a famous backbone is benchmarked against in every field | order them by cosine to the named area instead, which turns the same rows into MS MARCO MRR@10 and Cora node classification |
| cells read `76.41±1.70plus-or-minus` and `67.2%percent67.267.2\%` | MathML writes the spoken name of an operator next to the symbol | cut a cell at the first spoken operator name |

### The rough edge this question did not fix

Five of the six lines start at `Distributed Representations of Words and Phrases`, 2013.
The magnets are right for the question, which is DPR, ANCE, GCN, BERT, ColBERT and GraphRAG, but
the reach walk runs past them to the oldest node any of them can reach.

## The method table, the paper type and the composer

Three things the old graphiv had, rebuilt on the new retrieval. Measured cold on a question never
asked before, about whether catastrophic forgetting is solved.

### What each level now costs

| level | seconds | of which the table | of which the composer |
| --- | --- | --- | --- |
| 0 | 59.6 | 26.9 | 3.1 |
| 1 | 325.4 | 54.8 | 3.8 |
| 2 | 602.6 | 82.7 | 3.6 |

### The table, which every level now has

Rows are methods and not papers, so one paper can carry two and two papers can carry one.
Columns are designed per question by one model call, and at least two of them are closed, meaning
they carry a short list of options the answers must snap onto.

| level | methods | papers behind them | headline number filled | closed axes |
| --- | --- | --- | --- | --- |
| 0 | 20 | 19 | 0.85 | 3 |
| 1 | 36 | 36 | 0.81 | 2 |
| 2 | 61 | 58 | 0.69 | 2 |

The columns move with the question, which is the whole point.

| question | the closed axes the model chose |
| --- | --- |
| is the citation graph a query-time signal or baked in | `graph_integration` none, query time, pre-trained; `reranking_strategy` pointwise, listwise, none |
| have in-context models displaced boosted trees | `learning_paradigm` gradient boosting, in-context learning, supervised pretraining, generative modeling; `data_dependency` single table, cross-table, few-shot |
| is catastrophic forgetting solved | `forgetting_mitigation` none, regularization, memory replay, architectural expansion, gradient projection; `model_architecture` single, multi, transformer based |

Reading one closed column down is the answer to the question that was asked.

| question | the column that answers it |
| --- | --- |
| query time or baked in | query time 25, none 5, pre-trained 3 |
| in-context or boosted trees | in-context learning 29, supervised pretraining 13, gradient boosting 1 |

### The gaps, which are the empty cells of two closed axes once judged

A cross tabulation always has empty cells and most of them are combinations that cannot hold at
once, so the mechanical table is evidence and the verdict is a second call.

| question | unexplored | exists outside this table |
| --- | --- | --- |
| query time or baked in | pre-trained + listwise | none + pointwise, pre-trained + pointwise |
| in-context or boosted trees | gradient boosting + cross-table | 3 others |
| catastrophic forgetting | gradient projection + multi model | memory replay + multi model, none + transformer |

### The paper type

The reader already labeled every paper `foundational`, `core`, `frontier`, `adjacent`, `survey` or
`unrelated` for this question, and the label was thrown away after it dropped the rejects.
It now picks the rows of the table, which is what makes the table the frontier and not a history,
and it prints beside every paper in the state list, which turns a ranking into a reading order.

### The composer, and whether it invents anything

Four sections over a digest of what the other stages extracted, and nothing else.
Every claim about a paper ends in that paper's id, and a claim read off a count carries none,
because the counted blocks name no paper.

| run | ids cited | ids present in the digest |
| --- | --- | --- |
| catastrophic forgetting, level 0 | 12 | 12 |
| catastrophic forgetting, level 1 | 11 | 11 |
| catastrophic forgetting, level 2 | 14 | 14 |
| citation graph, level 0 | 12 | 12 |

### Two things the composer needed before it worked

| defect | cause | fix |
| --- | --- | --- |
| counts came out carrying a random paper id | the spread and gap blocks name no paper, so the model borrowed an id from elsewhere in the digest | the prompt now says which blocks are id bearing |
| the disagreement section said there was none | the quotes were read off the threads, and one critique edge sits on several threads at once, so four lines yielded the same three sentences | read them off every critique edge in the head instead, deduped by pair and ranked by the magnet weight of the target |
