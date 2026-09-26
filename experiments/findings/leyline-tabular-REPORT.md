# Leyline reachability on foundational tabular models

## Configuration

| item | value |
| --- | --- |
| query | `foundational tabular models` |
| retriever | cosine only, `hnsw.ef_search = 1000`, no bm25 index exists on `papers` |
| pool | 400, cosine 0.6327 .. 0.4315 |
| topic filter | parent vote over the whole pool, summed cosine |
| reader | Gemma-4-26B-Batched, prod prompt verbatim, `reasoning_effort: "none"` |
| landmark budget m | 120, leyline quota 8 |
| leyline | shipped constants, seeds 10, gamma 0.4, k 1, max_lineages 50 |

## The six tracked papers

| id | title | cosine | pool rank | topic | grade |
| --- | --- | --- | --- | --- | --- |
| 2207.01848 | TabPFN (2022) | 0.3759 | miss | leaf (1,13,5) | ungraded |
| 2502.05564 | TabICL | 0.5203 | 47 | keep | 2 frontier |
| 2511.08667 | TabPFN-2.5 | 0.5134 | 54 | keep | 2 frontier |
| 2605.13986 | TabPFN-3 | 0.4973 | 80 | keep | 2 frontier |
| 2602.11139 | TabICLv2 | 0.5297 | 32 | keep | 2 frontier |
| 2608.16429 | Localized TabICLv2 | none | miss | none | ungraded |

## Stage sizes

| stage | in | out |
| --- | --- | --- |
| cosine pool | 3,103,758 | 400 |
| topic filter, parent (1,13) | 400 | 185 |
| reader grades | 185 | 185 |
| magnets, relevance 2 | 185 | 49 |
| induced subgraph | 185 nodes | 628 distinct edges |
| fused head, m - quota | 179 rankable | 112 |
| leyline picks | 49 magnets | 0 |

## Reader grade distribution

| relevance | 2 | 1 | 0 | -1 | -2 |
| --- | --- | --- | --- | --- | --- |
| papers | 49 | 114 | 13 | 3 | 6 |

| role | frontier | survey | adjacent | unrelated | core |
| --- | --- | --- | --- | --- | --- |
| papers | 134 | 24 | 19 | 6 | 2 |

## Citation structure of the tracked papers

| id | pool citers | total citers | pool share |
| --- | --- | --- | --- |
| 2207.01848 | 76 | 470 | 0.162 |
| 2502.05564 | 54 | 170 | 0.318 |
| 2511.08667 | 29 | 102 | 0.284 |
| 2605.13986 | 7 | 25 | 0.280 |
| 2602.11139 | 20 | 66 | 0.303 |
| 2608.16429 | 0 | 0 | 0.000 |

`2608.16429` is at `stage = 0`: no PDF, no HTML, no embedding, no topic level, no citation row in
either direction.

## Reach saturation, 49 magnets over the connecting subgraph

![reach decay](figures/reach_decay.png)

| beta | rank of 2207.01848 by reach | top node by reach |
| --- | --- | --- |
| 1.0 | 114 | 1703.06490, Generating Multi-label Discrete Patient Records using GANs |
| 0.7 | 3 | 2207.01848 group |
| 0.5 | 2 | 2207.01848 group |
| 0.3 | 2 | 2207.01848 group |

With the fame gate applied (pool share >= 0.05, 561 nodes) the same sweep puts 2207.01848 at
rank 26 of 272 at beta 1.0 and rank 1 of 272 at beta 0.7, 0.5 and 0.3.

Top six by reach, fame-gated subgraph:

| beta 1.0 | beta 0.5 |
| --- | --- |
| 1907.00503 Modeling Tabular data using Conditional GAN | 2207.01848 TabPFN |
| 1908.07442 TabNet | 2012.06678 TabTransformer |
| 1703.06490 Discrete Patient Records via GANs | 1908.07442 TabNet |
| 1806.03384 Data Synthesis based on GANs | 2106.11959 Revisiting Deep Learning Models for Tabular Data |
| 1807.01202 Multi-Categorical Samples with GANs | 2106.01342 SAINT |
| 1807.01514 Synthetic but Plausible Healthcare Records | 2110.01889 Deep Neural Networks and Tabular Data: A Survey |

All top nodes at beta 1.0 tie at reach 41.00 of a possible 49.

## Discovery harvest, 20 papers outside the pool

Connecting subgraph: pool 185, backward candidates at >= 3 pool citers 256, forward candidates
287, 376 surviving the fame gate, 561 nodes and 5,207 edges.

| beta 1.0 | beta 0.5 |
| --- | --- |
| TabuLa: Language Models for Tabular Data Synthesis | TabNet |
| Large Language Models on Tabular Data | TabPFN (2022) |
| LimiX | TabPFN Unleashed |
| TabPFN Unleashed | Unreflected Use of Tabular Data Repositories |
| CTAB-GAN | Better by Default: Pre-Tuned MLPs and Boosted Trees |
| STaSy: Score-based Tabular data Synthesis | Towards Cross-Table Masked Pretraining |
| TabMT: masked transformers | LLMs Can Automatically Engineer Features |
| Why Tabular Foundation Models Should Be a Priority | Why Tabular Foundation Models Should Be a Priority |
| Retrieval & Fine-Tuning for In-Context Tabular Models | Retrieval & Fine-Tuning for In-Context Tabular Models |
| CTAB-GAN+ | Revisiting Nearest Neighbor for Tabular Data |
| Unreflected Use of Tabular Data Repositories | TALENT toolbox |
| TabNet | TabFlex: linear attention |
| TabDDPM | CausalPFN |
| Towards Cross-Table Masked Pretraining | TuneTables |
| Curated LLM | Zero-shot Meta-learning for Tabular Prediction |
| Understanding the Limits of Deep Tabular Methods | Understanding the Limits of Deep Tabular Methods |
| Towards Universal Neural Likelihood Inference | LimiX |
| On the Usefulness of Synthetic Tabular Data | Rethinking Pre-Training in Tabular Data |
| Generating and Imputing Tabular Data via Diffusion | TabRepo |
| Rethinking Pre-Training in Tabular Data | Survey on Self-Supervised Learning for Tabular |

## Reachability of the six, by mechanism

| id | cosine | topic | ancestors | leyline prod | leyline discovery |
| --- | --- | --- | --- | --- | --- |
| 2207.01848 | no | n/a | yes, 76 pool citers | no | yes at beta < 1, no at beta 1.0 |
| 2502.05564 | yes | keep | n/a | in head | n/a |
| 2511.08667 | yes | keep | n/a | in head | n/a |
| 2605.13986 | yes | keep | n/a | in head | n/a |
| 2602.11139 | yes | keep | n/a | in head | n/a |
| 2608.16429 | no | no | no | no | no |

## Files

| file | what |
| --- | --- |
| `common.py` | store, endpoints, the tracked ids |
| `stage_a_pool.py` | cosine pool |
| `stage_b_topic.py` | parent-vote topic filter |
| `stage_c_grade.py` | reader grades, cached in `cache/grades.json` |
| `leyline.py` | the walk, prod shape plus `beta` and `collect_path` |
| `stage_d_leyline.py` | prod reproduction |
| `stage_e_discovery.py` | connecting subgraph and the outside-pool harvest |
| `figure.py` | `figures/reach_decay.png` |

---

# Part 2: why this area is hard to retrieve

Prompt under test:

> Do research on the topic of tabular neural networks (i.e. foundational model for tabular data)
> and why tabular model likes vector input instead of just scalar (making it so turning scalar
> inputs into embedding somehow leads to better perf)

## TabPFN v2 is not in the corpus, and cannot be

Every arXiv paper by the first author, in date order:

| id | date | title |
| --- | --- | --- |
| 2112.10510 | 2021-12-20 | Transformers Can Do Bayesian Inference |
| 2207.01848 | 2022-07-05 | TabPFN: A Transformer That Solves Small Tabular Classification Problems |
| 2411.10634 | 2024-11-15 | Drift-Resilient TabPFN |
| 2511.08667 | 2025-11-11 | TabPFN-2.5 |
| 2605.13986 | 2026-05-13 | TabPFN-3: Technical Report |

| probe | rows |
| --- | --- |
| `title ILIKE '%accurate predictions on small data%'` | 0 |
| `doi ILIKE '%s41586-024-08328%'` | 0 |

Citation occurrences whose sentence names TabPFNv2, by what the resolver matched:

| target | resolved_by | occurrences |
| --- | --- | --- |
| UNRESOLVED | none | 277 |
| 2511.08667 | text | 44 |
| 2509.03505 | text | 23 |
| 2207.01848 | title-exact | 20 |
| 2502.05564 | text | 19 |
| UNRESOLVED | rejected-overlap | 16 |
| 1603.02754 (XGBoost) | title-exact | 13 |
| 1706.09516 (CatBoost) | title-exact | 9 |

## Exact rank over all 3,103,758 embedded papers

| paper | level | full prompt | clause A | clause B | short |
| --- | --- | --- | --- | --- | --- |
| TabPFN-2.5 | (1,13,5) | 349 | 101 | 4,399 | 55 |
| TabPFN 1.0 | (1,13,5) | 491 | 402 | 5,334 | 2,168 |
| TabICL | (1,13,5) | 203 | 98 | 1,048 | 48 |
| TabICLv2 | (1,13,5) | 153 | 107 | 616 | 33 |
| TabPFN-3 | (1,13,5) | 211 | 194 | 673 | 81 |
| Numerical Feature Embeddings | (1,13,5) | 13 | 472 | 1 | 1,555 |
| Revisiting DL Models | (1,13,5) | 18 | 27 | 123 | 211 |

clause A: `tabular neural networks, foundational model for tabular data`
clause B: `why tabular models like vector input instead of scalar, turning scalar inputs into
embeddings leads to better performance`

## Clause-B vocabulary count in title plus abstract

| paper | embedding | scalar | vector | representation | tokeniz | encoding | numerical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TabPFN-2.5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TabPFN 1.0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| TabICL | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| TabICLv2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TabPFN-3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Numerical Feature Embeddings | 8 | 2 | 0 | 0 | 0 | 1 | 5 |
| Revisiting DL Models | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Neighbourhood compression, cosine at rank

| query | 1 | 10 | 50 | 100 | 400 | 1000 | r1 - r400 | r1 - r1000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full | 0.6925 | 0.6536 | 0.6127 | 0.5935 | 0.5434 | 0.5061 | 0.1491 | 0.1864 |
| A | 0.6739 | 0.6333 | 0.5834 | 0.5634 | 0.5009 | 0.4518 | 0.1730 | 0.2221 |
| B | 0.6192 | 0.5490 | 0.5168 | 0.4960 | 0.4603 | 0.4358 | 0.1590 | 0.1834 |
| short | 0.6327 | 0.5791 | 0.5197 | 0.4872 | 0.4315 | 0.3956 | 0.2012 | 0.2371 |

## Top-400 overlap between the queries

| pair | papers in common |
| --- | --- |
| full & A | 291 |
| full & B | 219 |
| A & B | 160 |
| full only, in neither clause's top 400 | 46 |

## Topic tree resolution

| node | name | papers |
| --- | --- | --- |
| leaf (1,13,5) | Tabular Foundation Models and Pretraining | 452 |
| parent (1,13) | Machine Learning Reliability | 7,878 |

All seven tracked papers are in leaf (1,13,5). 210 of that leaf's 452 papers are in the
full-prompt top 400. The parent vote picks (1,13) under all four queries.

## Position through the pipeline, full prompt

| paper | cosine rank in 400 | after topic (248) | reader | fused rank | inside m=120 |
| --- | --- | --- | --- | --- | --- |
| Numerical Feature Embeddings | 12 | 12 | 2 core | 9 | yes |
| Revisiting DL Models | 17 | 17 | 1 survey | 94 | yes |
| TabICLv2 | 116 | 116 | 2 frontier | 53 | yes |
| TabICL | 146 | 146 | 2 frontier | 64 | yes |
| TabPFN-3 | 150 | 150 | 2 frontier | 65 | yes |
| TabPFN-2.5 | 224 | 224 | 2 frontier | 81 | yes |

Reader relevance over the 248: 87 at 2, 123 at 1, 29 at 0, 6 at -1, 3 at -2.

## Effort tier sweep, full prompt

| tier | n_pool | m | after topic | TabPFN-2.5 | TabICLv2 | TabPFN-3 | Numerical Emb |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tiny | 200 | 30 | 145 | not in pool | graded (deg) | not in pool | graded (cos) |
| fast | 400 | 60 | 248 | graded (deg) | graded (cos) | graded (deg) | graded (cos) |
| standard | 400 | 90 | 248 | graded (deg) | graded (cos) | graded (cos) | graded (cos) |
| deep | 600 | 120 | 330 | graded (cos) | graded (cos) | graded (cos) | graded (cos) |

`graded (deg)` means the paper entered the reader's candidate set only through the top-2m
in-degree half, never through the top-2m cosine half.

## Split the query, RRF over the two clause pools, c=60

| paper | full-prompt rank | fused rank | inside a 400 pool |
| --- | --- | --- | --- |
| Numerical Feature Embeddings | 13 | 33 | yes |
| Revisiting DL Models | 18 | 28 | yes |
| TabICL | 202 | 231 | yes |
| TabPFN-2.5 | 345 | 238 | yes |
| TabICLv2 | 153 | 251 | yes |
| TabPFN-3 | 210 | 349 | yes |
| TabPFN 1.0 | 481 | 636 | no |

## Index ceiling

`hnsw.ef_search` has a hard maximum of 1000 in pgvector. A query with `LIMIT 3000` and
`ef_search = 1000` silently returns 1000 rows. Anything past cosine rank 1000 is unreachable by
vector search at any `n_pool`.

| paper | query where it sits past 1000 | exact rank |
| --- | --- | --- |
| TabPFN-2.5 | clause B | 4,399 |
| TabPFN 1.0 | clause B | 5,334 |
| TabPFN 1.0 | short | 2,168 |
| TabICL | clause B | 1,048 |
| Numerical Feature Embeddings | short | 1,555 |

## Files added in part 2

| file | what |
| --- | --- |
| `diag_query.py` | rank of each tracked paper per query variant |
| `diag_deep.py` | compression, overlap, vocabulary, topic vote, exact ranks, split-and-fuse |
| `diag_final.py` | leaf resolution and per-paper vocabulary counts |
| `diag_grade_full.py` | grades and fused ranks under the real prompt |
| `diag_budget.py` | effort tier sweep |
