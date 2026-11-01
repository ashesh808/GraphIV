# survey-agreement

How much two surveys on the same topic, written within three months of each other, share a
bibliography. This is the human ceiling for SurveyMatch.

## Construction

| item | rule |
| --- | --- |
| candidates | survey-titled, stage 4, `level_2` set, dated 2023-01 or later |
| pairing | same `level_2` leaf, second survey within 3 months of the first |
| reference set | resolved stage-4 references dated on or before the earlier survey's date |
| kept | both bibliographies at least 25 references |
| similarity | cosine between the two surveys' own `embed_full` |

| quantity | value |
| --- | --- |
| same-leaf pairs within 3 months | 59,516 |
| pairs with both bibliographies >= 25 | 24,370 |
| distinct surveys | 2,194 |
| median gap | 46 days |
| median references per survey | 76 |

## Agreement over all same-leaf pairs

| measure | p10 | p25 | p50 | p75 | p90 | mean |
| --- | --- | --- | --- | --- | --- | --- |
| jaccard | 0.000 | 0.000 | 0.000 | 0.006 | 0.016 | 0.006 |
| overlap coefficient | 0.000 | 0.000 | 0.000 | 0.018 | 0.051 | 0.018 |
| shared references | 0 | 0 | 0 | 1 | 3 | 1.4 |

| overlap coefficient | pairs | share |
| --- | --- | --- |
| 0.00 to 0.05 | 21,858 | 89.7% |
| 0.05 to 0.10 | 1,553 | 6.4% |
| 0.10 to 0.20 | 651 | 2.7% |
| 0.20 to 0.30 | 153 | 0.6% |
| 0.30 to 0.50 | 116 | 0.5% |
| 0.50 and up | 39 | 0.2% |

## Agreement by how similar the two surveys actually are

| survey-to-survey cosine | pairs | jaccard | overlap | p90 overlap | references each |
| --- | --- | --- | --- | --- | --- |
| 0.00 to 0.70 | 23,866 | 0.004 | 0.014 | 0.044 | 61 |
| 0.70 to 0.80 | 411 | 0.055 | 0.152 | 0.341 | 88 |
| 0.80 to 0.85 | 62 | 0.125 | 0.320 | 0.558 | 90 |
| 0.85 to 0.90 | 29 | 0.160 | 0.350 | 0.497 | 112 |
| 0.90 and up | 2 | | 0.716 | | |

## The closest pairs

| cosine | overlap | shared | gap | titles |
| --- | --- | --- | --- | --- |
| 0.967 | 0.84 | 32/38 | 31d | A Survey of Foundation Models for Environmental Science / Foundation Models for Environmental Science |
| 0.912 | 0.59 | 36/61 | 88d | A Survey on Hallucination in Large Vision-Language Models / Hallucination of Multimodal Large Language Models |
| 0.89 | 0.75 | 74/99 | 26d | Stop Overthinking: A Survey on Efficient Reasoning / Efficient Reasoning Models: A Survey |
| 0.88 | 0.72 | 80/111 | 20d | A Survey on Feedback-based Multi-step Reasoning / Towards Reasoning Era: A Survey of Long Chain-of-Thought |

## Our system at the same budget

Twenty FrontierMatch pairs, lineage key, recall at k.

| arm | 50 | 100 | 200 | 500 | 1000 |
| --- | --- | --- | --- | --- | --- |
| graph, hub 0.3 | 0.237 | 0.328 | 0.459 | 0.634 | 0.767 |
| graph, hub 0.7 | 0.198 | 0.298 | 0.420 | 0.604 | 0.751 |
| cosine | 0.058 | 0.080 | 0.129 | 0.201 | 0.267 |

Frontier key, same runs.

| arm | 50 | 100 | 200 | 500 | 1000 |
| --- | --- | --- | --- | --- | --- |
| peer recent, hub 0.7 | 0.101 | 0.146 | 0.249 | 0.420 | 0.582 |
| graph, hub 0.7 | 0.031 | 0.059 | 0.107 | 0.241 | 0.415 |
| cosine | 0.013 | 0.029 | 0.048 | 0.109 | 0.186 |

| comparison at a survey-sized budget | value |
| --- | --- |
| two expert surveys, cosine 0.80 to 0.90, references each 90 to 112 | 0.320 to 0.350 |
| our ranker at k=100 | 0.328 |
| our ranker at k=1000 | 0.767 |

## Files

```
main.py    the pairs and the raw agreement
bycos.py   agreement binned by survey-to-survey cosine
pairs.json 24,370 pairs with both bibliographies and their overlap
```

## Recall, and our ranker on the same held-out key

Agreement expressed as recall rather than overlap coefficient, both directions, all 24,370 pairs
binned by how similar the two surveys are.

| survey-to-survey cosine | pairs | recall A of B | recall B of A | both | p90 | key size |
| --- | --- | --- | --- | --- | --- | --- |
| 0.00 to 0.70 | 23,866 | 0.011 | 0.010 | 0.010 | 0.033 | 98 |
| 0.70 to 0.80 | 411 | 0.117 | 0.113 | 0.115 | 0.265 | 134 |
| 0.80 to 0.85 | 62 | 0.267 | 0.224 | 0.245 | 0.484 | 120 |
| 0.85 to 0.90 | 29 | 0.292 | 0.290 | 0.291 | 0.421 | 148 |
| 0.90 and up | 2 | 0.303 | 0.716 | 0.510 | 0.767 | 114 |

All 93 pairs at cosine 0.80 or above: mean recall 0.265, median 0.257, p90 0.491, mean key 129.

### Held-out comparison

The 25 highest-cosine pairs. Query is reviewer 1's title with the boilerplate stripped, answer
key is reviewer 2's bibliography, retrieval capped at the earlier of the two dates. Reviewer 1's
own bibliography is scored on the same key, so the two rows answer the same question.

| who | budget | recall against reviewer 2 |
| --- | --- | --- |
| reviewer 1, a human expert | 141 | 0.301 |
| our ranker, k=100 | 100 | 0.281 |
| our ranker, k=129 | 129 | 0.319 |
| our ranker, k=1000 | 1000 | 0.656 |

| arm | 50 | 100 | 129 | 200 | 500 | 1000 |
| --- | --- | --- | --- | --- | --- | --- |
| graph, hub 0.3 | 0.188 | 0.281 | 0.319 | 0.390 | 0.553 | 0.656 |
| graph, hub 0.7 | 0.183 | 0.289 | 0.324 | 0.398 | 0.552 | 0.652 |
| peer recent, hub 0.7 | 0.126 | 0.192 | 0.218 | 0.265 | 0.420 | 0.552 |
| cosine | 0.137 | 0.202 | 0.233 | 0.275 | 0.377 | 0.446 |

Scoring against a different expert's bibliography rather than the author of the query gives
0.656 at k=1000, against 0.647 on SurveyMatch, so the SurveyMatch number is not an artifact of
scoring against the author who wrote the query.

## Files

```
main.py       the pairs and the raw agreement
bycos.py      agreement binned by survey-to-survey cosine
vs2.py        retrieval for the 25 highest-cosine pairs
scorevs2.py   reviewer 1 and our ranker, both against reviewer 2's key
pairs.json    24,370 pairs with both bibliographies and their overlap
cases/        the 25 retrieval cases
```
