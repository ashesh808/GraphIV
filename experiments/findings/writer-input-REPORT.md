# writer-input

What to hand a report writer, measured on one survey and on the corpus.

## Configuration

| item | value |
| --- | --- |
| case | `2509.11570`, Bhaasha, Bhasa, Zaban: A Survey for Low-Resourced Languages in South Asia |
| survey date | 2025-09-15 |
| references used | 68, each with local html and at least 3 external citation contexts |
| held out target | the survey's own sentences citing each reference, never shown to any arm |
| model | Gemma-4-26B-HighBatched, 16 slots, `reasoning_effort` none |
| embedding | nomic-embed-text-v2-moe at 127.0.0.1:11435 |
| corpus sample | 8,000 source papers, 617,305 labeled citations, 509,307 positioned |

## Schema fill, by evidence source

Fixed five-field schema. Evidence is the mean prompt size in characters.

| arm | parsed | unknown fields | evidence | wall |
| --- | --- | --- | --- | --- |
| abstract | 68/68 | 15 | 1,692 | 32.6s |
| fulltext | 68/68 | 11 | 16,690 | 121.7s |
| context | 68/68 | 59 | 5,457 | 63.7s |
| abs+ctx | 68/68 | 7 | 6,711 | 72.2s |

## Unknown fields per field, of 68 papers

| arm | problem | method | data | finding | relation |
| --- | --- | --- | --- | --- | --- |
| abstract | 0 | 0 | 6 | 0 | 9 |
| fulltext | 2 | 2 | 3 | 2 | 2 |
| context | 1 | 8 | 25 | 24 | 1 |
| abs+ctx | 0 | 0 | 6 | 0 | 1 |

## Coverage of the survey's held-out sentences

Judge answers yes, partly or no. Score is `(yes + 0.5 partly) / n`.

| arm | yes | partly | no | score |
| --- | --- | --- | --- | --- |
| abstract | 12 | 28 | 28 | 0.382 |
| fulltext | 13 | 26 | 29 | 0.382 |
| context | 10 | 28 | 30 | 0.353 |
| abs+ctx | 12 | 30 | 26 | 0.397 |

## Record separation, mean pairwise cosine over 68 papers

| source | whole record | problem | method | data | finding | relation |
| --- | --- | --- | --- | --- | --- | --- |
| abstracts, reference | 0.5061 | | | | | |
| abstract | 0.5109 | 0.5756 | 0.4628 | 0.5494 | 0.4551 | 0.5508 |
| fulltext | 0.5066 | 0.5609 | 0.4556 | 0.5274 | 0.4495 | 0.5341 |
| context | 0.5205 | 0.6018 | 0.4980 | 0.5716 | 0.5465 | 0.5591 |
| abs+ctx | 0.5113 | 0.5735 | 0.4626 | 0.5281 | 0.4589 | 0.5727 |

## Citation position against intent, corpus wide

Position is the citing paper's top-level section number, normalized to 0 at its first section and 1 at its last.
Only papers with at least four top-level sections contribute.

| intent | mean position | sd | median | n |
| --- | --- | --- | --- | --- |
| motivates | 0.321 | 0.334 | 0.250 | 4,460 |
| critiques | 0.363 | 0.358 | 0.273 | 18,633 |
| background | 0.371 | 0.353 | 0.333 | 363,491 |
| extends | 0.407 | 0.348 | 0.333 | 15,696 |
| uses | 0.559 | 0.316 | 0.600 | 71,213 |
| compares | 0.611 | 0.343 | 0.667 | 35,814 |
| all | 0.414 | 0.357 | | 509,307 |

## Intent share inside each position quintile

| quintile | background | compares | critiques | extends | motivates | uses |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 83.5% | 3.2% | 4.6% | 2.9% | 1.2% | 4.6% |
| 2 | 75.4% | 4.0% | 3.5% | 3.3% | 0.8% | 13.0% |
| 3 | 68.7% | 5.9% | 3.4% | 3.5% | 0.8% | 17.7% |
| 4 | 61.7% | 10.6% | 3.1% | 2.9% | 0.8% | 20.9% |
| 5 | 61.9% | 13.1% | 3.2% | 2.9% | 0.5% | 18.3% |

## Same signal on the case cohort

272,041 citations of the 68 cohort papers, 115,410 positioned.

| intent | mean position | sd | n |
| --- | --- | --- | --- |
| critiques | 0.440 | 0.431 | 3,382 |
| background | 0.505 | 0.416 | 55,623 |
| motivates | 0.537 | 0.401 | 1,672 |
| extends | 0.630 | 0.382 | 3,249 |
| compares | 0.762 | 0.363 | 8,272 |
| uses | 0.808 | 0.303 | 43,212 |

## Cohort papers by mean citation position, at least 30 positioned citations

| position | n | title |
| --- | --- | --- |
| 0.428 | 43 | One Country, 700+ Languages: NLP Challenges for Underrepresented Languages |
| 0.471 | 123 | Language Model Tokenizers Introduce Unfairness Between Languages |
| 0.517 | 41 | MaLA-500: Massive Language Adaptation of Large Language Models |
| ... | | |
| 0.717 | 1,465 | Enriching Word Vectors with Subword Information |
| 0.725 | 4,371 | Mistral 7B |
| 0.726 | 4,106 | Measuring Massive Multitask Language Understanding |

## Relation checkability inside the cohort

2,276 time-ordered pairs among the 68 papers.
A pair is checkable when a resolved citation edge exists between the two.

| cosine band | pairs | with edge | rate | typed edge | edge carries a sentence |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.5 | 1,199 | 51 | 0.043 | 32 | 51 |
| 0.5-0.6 | 816 | 53 | 0.065 | 32 | 52 |
| 0.6-0.7 | 244 | 37 | 0.152 | 19 | 36 |
| 0.7-0.8 | 17 | 4 | 0.235 | 3 | 4 |
| 0.8-1.0 | 0 | 0 | 0.000 | 0 | 0 |
| 200 most similar | 200 | 34 | 0.170 | | |

## Chain mining on the cohort neighborhood

| item | value |
| --- | --- |
| cohort | 68 |
| connectors pulled in | 300 |
| nodes after stage-4 filter | 368 |
| citation edges among them | 9,959 |
| forward-in-time edges, best sentence kept | 4,299 |
| of those, technical rather than background | 2,127, 49.5% |
| chains of length 4 | 14,892 |

## Schema fill, by who wrote the schema

Evidence held at abstract plus citation context for all three.

| schema | parsed | score against held-out sentences |
| --- | --- | --- |
| static, five fixed fields | 68/68 | 0.390 |
| dyn-query, proposed from the survey title alone | 68/68 | 0.368 |
| dyn-sample, proposed after seeing 12 cohort abstracts | 68/68 | 0.375 |

Fields proposed by each.

| schema | fields |
| --- | --- |
| static | problem, method, data, finding, relation |
| dyn-query | language, task, resource, methodology, metric |
| dyn-sample | objective, methodology, language_scope, contribution_type, evaluation_metric |

## Writer input, date sorted list against justified trajectory

Same four papers, same instruction, one paragraph each.
Transitions are quoted verbatim from the two outputs.

| chain | date sorted transition | justified transition |
| --- | --- | --- |
| PaLM to Llama 2 | "progresses toward the release of open-source alternatives" | "which introduced specific techniques for detecting data contamination via 8-gram analysis" |
| Gemma to MMLU-Pro | "Evaluation methodologies then evolved with the introduction of" | "which extended existing datasets by adding reasoning-focused questions and expanding answer choices" |
| multilingual CoT to cross-lingual prompting | "Subsequent research refined these techniques" | "expanded these concepts by incorporating implicit or explicit translation into the intermediate stages of prompting" |

The PaLM 2 to Gemma hop carries no sentence in the store.
The justified paragraph writes "This was followed by the introduction of the Gemma models" and names no mechanism there.

## Example mined chain

| date | id | title | hop |
| --- | --- | --- | --- |
| 2017-06-12 | 1706.03762 | Attention Is All You Need | |
| 2019-10-25 | 1910.11856 | On the Cross-lingual Transferability of Monolingual Representations | uses: "jointly training a transformer model (Vaswani et al., [CITE]) to perform masked language..." |
| 2020-10-22 | 2010.11934 | mT5: A massively multilingual pre-trained text-to-text transformer | uses: "we evaluate our models on 6 tasks from the xtreme multilingual benchmark" |
| 2024-01-19 | 2401.10695 | LangBridge: Multilingual Reasoning Without Multilingual Supervision | uses: "we use the encoders of mT5 (Xue et al., [CITE]) as the multilingual encoders" |

## Files

| file | what it does |
| --- | --- |
| `fixture.py` | picks the survey, pulls references, held-out sentences and external contexts to `case.json` |
| `distill.py` | four evidence arms into a fixed schema, to `records.json` |
| `dynamic.py` | three schema arms on fixed evidence, to `records_dyn.json` |
| `score.py` | judges a record set against the held-out sentences, to `judged.json` |
| `analyze.py` | per-field unknown counts and record separation by embedding |
| `intent.py`, `intent2.py` | section buckets and normalized citation position on the cohort |
| `position.py` | the same position measurement on an 8,000 paper corpus sample |
| `verify.py` | how often a time-ordered cohort pair carries a resolved edge |
| `traj.py` | mines forward-in-time chains with a sentence on every hop, to `chains.json` |
| `write.py` | one chain to the writer twice, as a list and as a trajectory, to `writer.log` |

## Four cases, one config: Gemma-4-26B-Batched, 4 slots at 32,768

| case | field | refs | abstract | fulltext | context | abs+ctx |
| --- || --- | --- | --- | --- | --- | --- |
| 2510.21887 | cs.CV | 80 | 0.475 | 0.481 | 0.469 | 0.475 |
| 2508.02121 | cs.AI | 77 | 0.571 | 0.545 | 0.584 | 0.584 |
| 2601.03181 | cs.NI | 161 | 0.619 | 0.661 | 0.575 | 0.625 |
| 2509.11570 | cs.CL | 68 | 0.397 | 0.426 | 0.382 | 0.375 |

### Total unknown fields

| case | abstract | fulltext | context | abs+ctx |
| --- | --- | --- | --- | --- |
| 2510.21887 | 42 | 17 | 91 | 28 |
| 2508.02121 | 21 | 39 | 77 | 15 |
| 2601.03181 | 61 | 36 | 144 | 41 |
| 2509.11570 | 16 | 10 | 52 | 5 |

### The relation field alone, unknown count

| case | abstract | fulltext | context | abs+ctx |
| --- | --- | --- | --- | --- |
| 2510.21887 | 9 | 1 | 0 | 0 |
| 2508.02121 | 4 | 8 | 1 | 0 |
| 2601.03181 | 14 | 3 | 1 | 0 |
| 2509.11570 | 12 | 2 | 1 | 1 |

### The data field alone, unknown count

| case | abstract | fulltext | context | abs+ctx |
| --- | --- | --- | --- | --- |
| 2510.21887 | 32 | 13 | 62 | 26 |
| 2508.02121 | 17 | 10 | 55 | 15 |
| 2601.03181 | 47 | 26 | 103 | 41 |
| 2509.11570 | 4 | 2 | 24 | 4 |

### Relation checkability

| case | time ordered pairs | edges | top 200 checkable |
| --- | --- | --- | --- |
| 2510.21887 | 3159 | 202 | 0.285 |
| 2508.02121 | 2924 | 205 | 0.275 |
| 2601.03181 | 12869 | 527 | 0.325 |
| 2509.11570 | 2276 | 145 | 0.170 |

### Spread

| | value |
| --- | --- |
| mean score per run | abstract 0.5156, fulltext 0.5287, context 0.5026, abs+ctx 0.5149 |
| widest spread within one case | 0.086 |
| spread between cases, abstract | 0.222 |
