# Six term pool score

Implements the score as specified: five channels, each with its own jury size and exponent,
plus a hub denominator.
`COC` blends the two citation walk directions, co-citation at `ALPHA` 0 and coupling at 1.

`main.py <query>` writes every table below into `figures/<query slug>_<name>.md`.

## Configuration

| constant | value | what it sets |
| --- | --- | --- |
| `TOP_K_QUERY` | 5000 | seed size by cosine |
| `TOP_K_CORE` | 200 | anchor for the one hop pool expansion |
| `TOP_K_ANC` | 200 | jury for `ANC` |
| `TOP_K_FRO` | 200 | jury for `FRO` |
| `TOP_K_COC` | 200 | jury for `COC` |
| `HOP_LIMIT` | 20000 | cap per hop direction |
| `C_COSINE` | 0.5 | exponent |
| `C_RECENCY` | 1.0 | exponent |
| `C_ANC` | 2.0 | exponent |
| `C_FRO` | 1.0 | exponent |
| `C_COC` | 2.0 | exponent |
| `C_HUB` | 0.3 | denominator exponent, named here since `ALPHA` now blends `COC` |
| `ALPHA` | 0.5 | `COC` blend |
| `LOG_SCALE` | 100 | inside `lg`, the multiplier that makes `log1p` compress |
| `EF_SEARCH` | 1000 | pgvector cap on rows returned |

| query | N | edges |
| --- | --- | --- |
| foundation models for tabular data | 9,044 | 86,895 |
| local LLM inference and serving | 8,695 | 96,236 |
| detection of gravitational waves from binary black holes | 18,510 | 258,554 |

## Channel support

| query | ANC nonzero | FRO nonzero | COC nonzero |
| --- | --- | --- | --- |
| tabular | 32.4% | 27.3% | 78.8% |
| LLM serving | 30.4% | 21.9% | 86.4% |
| grav. waves | 23.1% | 76.5% | 98.6% |

## Spearman between channels, tabular / LLM serving / grav. waves

| pair | rho |
| --- | --- |
| ANC ~ FRO | -0.201 / -0.206 / -0.249 |
| ANC ~ COC | 0.126 / 0.024 / -0.084 |
| FRO ~ COC | 0.501 / 0.365 / 0.614 |
| ANC ~ cos | -0.404 / -0.515 / 0.102 |
| ANC ~ cited | 0.661 / 0.667 / 0.524 |
| COC ~ rec | 0.424 / 0.322 / 0.628 |
| rec ~ cited | -0.551 / -0.673 / -0.495 |

## Dynamic range per term, p99 over p1

| term | tabular | LLM serving | grav. waves |
| --- | --- | --- | --- |
| `cos ** C_COSINE` | 1.9x | 1.8x | 1.8x |
| `rec ** C_RECENCY` | 21.1x | 16.1x | 26.8x |
| `(1+rec) ** C_RECENCY` | 1.9x | 1.9x | 1.9x |
| `(1+lg ANC) ** C_ANC` | 2.3x | 2.4x | 2.2x |
| `(1+lg FRO) ** C_FRO` | 1.7x | 1.7x | 1.7x |
| `(1+lg COC) ** C_COC` | 3.2x | 3.2x | 2.7x |
| `1 / (1+cited) ** C_HUB` | 12.5x | 11.8x | 6.9x |
| `1 / (1+lg cited) ** C_HUB` | 1.1x | 1.1x | 1.0x |

## Top 1000 composition, as specified against bounded recency and hub

Bounded replaces `nz(rec) ** C` with `(1 + nz(rec)) ** C` and `(1 + cited) ** C` with
`(1 + lg(cited)) ** C`, putting every term on `[1, 2 ** C]`.

| query | form | median year | mean cited | mean cosine | share with ANC > 0 |
| --- | --- | --- | --- | --- | --- |
| tabular | as specified | 2026 | 2 | 0.3849 | 15% |
| tabular | bounded | 2025 | 258 | 0.4081 | 39% |
| LLM serving | as specified | 2026 | 1 | 0.3699 | 5% |
| LLM serving | bounded | 2025 | 289 | 0.3705 | 32% |
| grav. waves | as specified | 2026 | 1 | 0.4697 | 1% |
| grav. waves | bounded | 2024 | 141 | 0.5399 | 54% |

## ALPHA sweep, top 1000 as specified

| alpha | tabular overlap with alpha 0 | LLM serving | grav. waves |
| --- | --- | --- | --- |
| 0.00 | 1000/1000 | 1000/1000 | 1000/1000 |
| 0.25 | 793/1000 | 752/1000 | 902/1000 |
| 0.50 | 771/1000 | 750/1000 | 887/1000 |
| 0.75 | 765/1000 | 748/1000 | 887/1000 |
| 1.00 | 761/1000 | 748/1000 | 888/1000 |

Median year is 2026 at every alpha in every query.

## Constant sensitivity, top 1000 overlap between the ends of each range

| constant | range | tabular | LLM serving | grav. waves |
| --- | --- | --- | --- | --- |
| `C_COSINE` | 0 to 1 | 859/1000 | 903/1000 | 874/1000 |
| `C_RECENCY` | 0 to 2 | 644/1000 | 650/1000 | 613/1000 |
| `C_ANC` | 0 to 4 | 853/1000 | 892/1000 | 984/1000 |
| `C_FRO` | 0 to 4 | 667/1000 | 491/1000 | 796/1000 |
| `C_COC` | 0 to 4 | 671/1000 | 629/1000 | 783/1000 |
| `C_HUB` | 0 to 1 | 643/1000 | 608/1000 | 620/1000 |

## Top 10, foundation models for tabular data

| rank | as specified | bounded |
| --- | --- | --- |
| 1 | Beyond IID: How General Are Tabular Foundation Models | TabICLv2 |
| 2 | TabDPT-Turbo | Mitra: Mixed Synthetic Priors |
| 3 | TabSwift | TabDPT |
| 4 | Memory Efficient Tabular Foundation Models | TabICL |
| 5 | Tabular Foundation Models for Discrete Choice | TabPFN-3 |
| 6 | SkillTFM | TabArena |
| 7 | Foundation Models for Credit Risk Prediction | A Closer Look at TabPFN v2 |
| 8 | TACTICL | Beyond IID |
| 9 | From field-scale to large-scale spectral libraries | LimiX |
| 10 | Topological Signatures of Context-Level Reliability | Representation Learning for Tabular Data |

| | as specified | bounded |
| --- | --- | --- |
| citations across the top 10 | 0 to 1 | 1 to 170 |
| papers with ANC > 0 | 5 / 10 | 10 / 10 |

## Open

| item | state |
| --- | --- |
| metric | not chosen, sweep not run |
| `C_HUB` under the bounded form | 1.1x range, likely needs a larger exponent |
| `TOP_K_ANC`, `TOP_K_FRO`, `TOP_K_COC` | all left at 200, never varied |
| `COC` multiplied by `rec` inside the channel and again by `C_RECENCY` outside | as specified |


# Constant sweep

`sweep.py` over 5 queries, pools cached from disk.
No metric is applied, so every column is a property of the returned top 1000.
"not in cosine top" is the share of the returned set that ranking by cosine alone would not return.

## One constant at a time, others at their defaults, mean over 5 queries

| constant | range | median year | median cited | mean cosine | ANC > 0 | not in cosine top |
| --- | --- | --- | --- | --- | --- | --- |
| `C_ANC` | 0 to 8 | 2025.2 to 2021.6 | 1.6 to 65.5 | 0.429 to 0.395 | 0.15 to 0.96 | 0.764 to 0.806 |
| `ALPHA` | 0 to 1 | 2022.8 to 2025.0 | 31.4 to 3.4 | 0.429 to 0.431 | 0.68 to 0.35 | 0.723 to 0.746 |
| `C_RECENCY` | 0 to 4 | 2023.4 to 2025.8 | 18.4 to 0.6 | 0.433 to 0.418 | 0.55 to 0.16 | 0.726 to 0.797 |
| `C_COC` | 0 to 8 | 2023.6 to 2024.8 | 12.2 to 3.8 | 0.444 to 0.424 | 0.51 to 0.31 | 0.697 to 0.774 |
| `C_COSINE` | 0 to 2 | 2025.0 to 2024.2 | 6.4 to 7.0 | 0.409 to 0.467 | 0.42 to 0.38 | 0.790 to 0.619 |
| `C_FRO` | 0 to 8 | 2024.8 to 2024.0 | 7.3 to 6.8 | 0.434 to 0.417 | 0.48 to 0.26 | 0.745 to 0.766 |
| `C_HUB` | 0 to 1.5 | 2024.4 to 2024.9 | 6.8 to 5.0 | 0.431 to 0.435 | 0.42 to 0.37 | 0.741 to 0.737 |

## Regimes, 1200 joint samples clustered on top 200 overlap

| regime | n | bounded | alpha | median year | median cited | ANC > 0 | not in cosine top |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 151 | 0.90 | 0.18 | 2023.1 | 27.6 | 0.601 | 0.747 |
| 4 | 752 | 0.58 | 0.54 | 2025.0 | 4.1 | 0.239 | 0.771 |
| 5 | 260 | 0.02 | 0.59 | 2025.7 | 0.05 | 0.046 | 0.827 |
| 0 | 16 | 0.06 | 0.09 | 2025.8 | 0.08 | 0.088 | 0.794 |
| 2 | 13 | 0.15 | 0.15 | 2025.8 | 0.06 | 0.055 | 0.845 |
| 3 | 8 | 0.00 | 0.34 | 2025.8 | 0.00 | 0.036 | 0.796 |

| regime | papers returned, tabular query |
| --- | --- |
| 1 | TabICL, TabDPT, TabArena, TabPFN v2, Mitra, LimiX, TabICLv2, TabPFN-3 |
| 0, 2, 3, 5 | Memory Efficient TFM, TabSwift, TabDPT-Turbo, Do TFMs Agree with Themselves, TFMs for Discrete Choice |

# Field read

`frontier.py` over 6 queries about publication retrieval, top 40 each, deduped, 2024 and newer.
Every abstract classified by `Gemma-4-26B-Batched` under a strict json schema, 140 of 140 parsed.

## Schema iterations

| schema | parsed | dense | citation graph | llm agent | no signal |
| --- | --- | --- | --- | --- | --- |
| signal as an uncapped list | 97 / 140 | 10 | 11 | 7 | 22% |
| list with `maxItems` | 140 / 140 | 21 | 20 | 12 | 56% |
| one boolean per signal | 140 / 140 | 52 | 14 | 30 | 34% |

An uncapped enum array never closes under constrained decoding, so the decode repeats one value to
the token cap and the drop is biased toward papers using more signals.
A list lets the model return the empty set, and a boolean per signal does not.

## What the 140 papers are for

| problem | papers |
| --- | --- |
| recommendation | 67 |
| review generation | 42 |
| search | 19 |
| graph analysis | 7 |
| benchmark or evaluation | 3 |
| position or survey | 2 |

90 of 140 propose a system, the rest are benchmarks, surveys and evaluations.

## Signals, over the 90 papers that propose a system

| signal | papers | share |
| --- | --- | --- |
| dense embedding | 44 | 49% |
| llm agent | 25 | 28% |
| full text | 17 | 19% |
| llm reranking | 14 | 16% |
| none | 14 | 16% |
| citation graph | 13 | 14% |
| lexical | 13 | 14% |
| metadata | 11 | 12% |

## Signal combinations, over the same 90

| combination | papers | share |
| --- | --- | --- |
| any llm | 36 | 40% |
| dense only | 23 | 26% |
| full text | 17 | 19% |
| graph at all | 13 | 14% |
| dense + any llm, no graph | 8 | 9% |
| graph + dense | 6 | 7% |
| graph + any llm | 5 | 6% |

## Papers using the citation graph

| year | title | signals |
| --- | --- | --- |
| 2026 | Rethinking Literature Search Evaluation: Deep Research Hel | citation graph+full text+llm agent+llm reranking+metadata |
| 2026 | Public Profile Matters: A Scalable Integrated Approach to  | citation graph+dense embedding+lexical+metadata |
| 2026 | Aspect-Aware Content-Based Recommendations for Mathematica | citation graph+dense embedding+metadata |
| 2026 | GRASP: Graph-Reasoning Aided Survey Planning for High-Fide | citation graph+llm agent |
| 2026 | The Scientific Contribution Graph: Automated Literature-ba | citation graph |
| 2026 | From Node2Vec to GPT-based GraphRAG: scientific impact pre | citation graph+dense embedding |
| 2025 | PaSa: An LLM Agent for Comprehensive Academic Paper Search | citation graph+full text+llm agent |
| 2025 | How Deep Do Large Language Models Internalize Scientific L | citation graph+metadata |
| 2025 | Select, Read, and Write: A Multi-Agent Framework of Full-T | citation graph+full text+llm agent |
| 2024 | Academic Article Recommendation Using Multiple Perspective | citation graph+dense embedding |
| 2024 | pathfinder: A Semantic Framework for Literature Review and | citation graph+dense embedding+llm reranking+metadata |
| 2024 | Shallow Synthesis of Knowledge in GPT-Generated Texts: A C | citation graph |
| 2024 | GRAG: Graph Retrieval-Augmented Generation | citation graph+dense embedding+full text |
| 2024 | KG-CTG: Citation Generation through Knowledge Graph-guided | citation graph |

## Evaluation

| | papers |
| --- | --- |
| names a benchmark | 105 |
| states none | 35 |
| distinct named evaluations | 105 |
| named evaluations used by more than one paper | 0 |
