# survey-match-grid

recall(limit, age) over 20 surveys, exact cosine ranks so nothing is truncated by `ef_search`.

## Configuration

| item | value |
| --- | --- |
| cases | `SurveyMatch(PG_DEST, n=20)`, ids in `cache.json` |
| corpus | 3,103,758 papers at stage 4 |
| candidate filter | `date < survey.date` |
| ranking | exact scan, `enable_indexscan = off`, 21.7s per survey |
| depth captured | top 20,000 per survey |
| answer key | the survey's own resolved stage-4 references |
| age | months before the survey date, applied to candidates and answer key alike |
| ancestors | targets of the top-400 cosine pool, `min_citers >= 2`, top 2,000 by distinct citers |

## Answer key size inside each window

| age | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mean refs per survey | 10.6 | 24.6 | 38.0 | 51.5 | 66.0 | 80.1 | 95.8 |

## recall(limit, age), cosine only

| limit | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 100 | 0.317 | 0.218 | 0.224 | 0.202 | 0.161 | 0.100 | 0.083 |
| 200 | 0.354 | 0.325 | 0.273 | 0.252 | 0.214 | 0.152 | 0.125 |
| 400 | 0.495 | 0.401 | 0.382 | 0.330 | 0.263 | 0.199 | 0.171 |
| 1000 | 0.618 | 0.529 | 0.488 | 0.442 | 0.381 | 0.316 | 0.256 |
| 2000 | 0.690 | 0.586 | 0.554 | 0.513 | 0.456 | 0.397 | 0.320 |
| 5000 | 0.806 | 0.700 | 0.658 | 0.615 | 0.560 | 0.521 | 0.441 |
| 10000 | 0.814 | 0.753 | 0.722 | 0.687 | 0.634 | 0.594 | 0.518 |
| 20000 | 0.814 | 0.753 | 0.737 | 0.717 | 0.680 | 0.657 | 0.616 |

## recall(limit, age) by arm, at a fixed slot budget

Budget 400

| arm | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cosine | 0.495 | 0.401 | 0.382 | 0.330 | 0.263 | 0.199 | 0.171 |
| ancestors | 0.143 | 0.238 | 0.289 | 0.350 | 0.356 | 0.383 | 0.361 |
| cosine 1/2 + anc 1/2 | 0.427 | 0.445 | 0.429 | 0.419 | 0.417 | 0.391 | **0.362** |
| cosine 3/4 + anc 1/4 | **0.524** | **0.451** | **0.476** | **0.392** | **0.385** | 0.360 | 0.318 |

Budget 1000

| arm | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cosine | 0.618 | 0.529 | 0.488 | 0.442 | 0.381 | 0.316 | 0.256 |
| ancestors | 0.143 | 0.238 | 0.306 | 0.393 | 0.418 | 0.466 | 0.489 |
| cosine 1/2 + anc 1/2 | 0.622 | 0.522 | 0.556 | **0.559** | **0.528** | **0.518** | **0.498** |
| cosine 3/4 + anc 1/4 | **0.665** | **0.568** | **0.569** | 0.552 | 0.527 | 0.483 | 0.451 |

Budget 2000

| arm | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cosine | 0.690 | 0.586 | 0.554 | 0.513 | 0.456 | 0.397 | 0.320 |
| ancestors | 0.143 | 0.238 | 0.306 | 0.394 | 0.432 | 0.494 | 0.552 |
| cosine 1/2 + anc 1/2 | 0.683 | 0.606 | 0.602 | 0.610 | 0.604 | 0.592 | **0.604** |
| cosine 3/4 + anc 1/4 | **0.714** | **0.631** | **0.633** | **0.632** | **0.611** | **0.593** | 0.575 |

Budget 5000

| arm | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cosine | 0.806 | 0.700 | 0.658 | 0.615 | 0.560 | 0.521 | 0.441 |
| ancestors | 0.143 | 0.238 | 0.306 | 0.394 | 0.432 | 0.494 | 0.552 |
| cosine 1/2 + anc 1/2 | 0.775 | 0.677 | 0.664 | 0.664 | 0.659 | 0.656 | 0.671 |
| cosine 3/4 + anc 1/4 | **0.819** | **0.715** | **0.701** | **0.694** | **0.684** | **0.679** | **0.685** |

The ancestor supply is capped at 2,000 fetched per survey and averages 1,556 after the date
filter, so every arm above 1,500 ancestor slots is supply-bound rather than budget-bound.

## Published numbers in the same shape

| benchmark | corpus | queries | metric | number |
| --- | --- | --- | --- | --- |
| SurGE `2508.15658` | 1.09M | 205 surveys | dense recall@1000 | 68.05 |
| RollingEval-Jun25 `2605.29234` | post-cutoff CS | 250 papers | recall @ K=10^4 | >80 |
| LitSearch `2407.18940` | 64K | 597 questions | GritLM recall@20 | 70.8 |
| **this run** | **3.10M** | **20 surveys** | **recall@1000, all ages** | **49.8** |
| **this run** | **3.10M** | **20 surveys** | **recall@5000, all ages** | **68.5** |

Protocol differences that block a direct comparison: the corpus here is 2.8x SurGE's, the query
is a boilerplate-stripped survey title rather than an expert-written topic description, and
LitSearch scores one target paper per question rather than a whole reference list.

## Correction made during this run

`analyze.py` first dated ancestors off the survey's own reference list, which filtered the
ancestor arm down to correct answers and reported 0.552 at every budget. Real dates were fetched
in `dates.py` and every arm number above is post-fix. The `arms()` block in `main.py` never had
the bug and its 0.4673 agrees with the corrected budget-800 row.

## Files

```
main.py       gathers exact ranks and ancestors, prints the cosine grid
dates.py      backfills real ancestor dates into cache.json
analyze.py    the arm comparison, reads cache.json only
cache.json    20 surveys, top-20,000 ranked ids, refs, ancestors
run.log       the gather run
```

## Candidate-generation ceiling per channel

Mean answer key is 95.8 references, so 1,000 slots is 10x the key and recall@1000 under a
perfect reranker equals the ceiling below. Forward means papers that cite the cosine-400 pool,
ancestors means papers it cites, both dated before the survey and at stage 4.

| channel | 6mo | 12mo | 18mo | 24mo | 36mo | 60mo | all | candidates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cosine 400 | 0.221 | 0.225 | 0.267 | 0.260 | 0.239 | 0.190 | 0.171 | 400 |
| cosine 1000 | 0.332 | 0.351 | 0.378 | 0.354 | 0.329 | 0.288 | 0.256 | 1,000 |
| cosine 20000 | 0.814 | 0.753 | 0.737 | 0.717 | 0.680 | 0.657 | 0.616 | 20,000 |
| ancestors of cos400 | 0.143 | 0.238 | 0.306 | 0.394 | 0.432 | 0.494 | 0.552 | 1,571 |
| forward of cos400 | 0.647 | 0.597 | 0.599 | 0.596 | 0.568 | 0.517 | 0.452 | 6,400 |
| cos400 + anc | 0.349 | 0.381 | 0.454 | 0.491 | 0.537 | 0.557 | 0.602 | 1,884 |
| cos400 + fwd | 0.669 | 0.632 | 0.628 | 0.627 | 0.600 | 0.547 | 0.484 | 6,569 |
| **cos400 + anc + fwd** | **0.726** | **0.681** | **0.689** | **0.721** | **0.729** | **0.728** | **0.743** | **7,685** |
| cos1000 + anc + fwd | 0.735 | 0.690 | 0.700 | 0.730 | 0.740 | 0.737 | 0.753 | 7,998 |
| cos20000 + anc + fwd | 0.899 | 0.852 | 0.838 | 0.834 | 0.824 | 0.824 | 0.830 | 24,338 |

## Where the references cosine-400 misses actually live

| bucket | count | share of the miss |
| --- | --- | --- |
| references, 20 surveys | 1,916 | |
| missed by cosine 400 | 1,603 | 83.7% of all references |
| ancestors only | 440 | 27.4% |
| forward only | 294 | 18.3% |
| both | 335 | 20.9% |
| neither | 534 | 33.3% |

## Implied split of the problem

| quantity | value |
| --- | --- |
| ceiling, 1 hop both directions off cosine-400 | 0.743 |
| candidates to rank | 7,685 |
| slots at k=1000 | 1,000 |
| references per survey | 95.8 |
| recall@1000 at random order within the candidate set | 0.097 |
