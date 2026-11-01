# grade-speed

Throughput of `Gemma-4-26B-HighBatched` on abstract grading, and whether the grades rerank
better than the graph ranking they are meant to improve.

## Configuration

| item | value |
| --- | --- |
| model | Gemma-4-26B-HighBatched, 16 slots at 131072/16 |
| endpoint | llama-router, `http://localhost:11434/v1` |
| body | `reasoning_effort: none`, `enable_thinking: false`, `temperature 0`, `max_tokens 24` |
| output | `{"relevance": N}` with N in -2..2 |
| case | survey `2504.21853`, 136 references, top 10,000 by the tuned graph ranking |
| GPU | one RTX 3090, otherwise idle |

## Throughput by concurrency, full abstracts

| concurrency | rows/s | p50 latency | p95 latency |
| --- | --- | --- | --- |
| 1 | 0.80 | 0.23s | 0.36s |
| 4 | 5.99 | 0.67s | 0.75s |
| 8 | 6.33 | 1.23s | 1.60s |
| 16 | 6.57 | 2.52s | 2.69s |
| 32 | 5.93 | 5.35s | 34.9s |
| 48 | 6.21 | 7.60s | 8.20s |

## Throughput by abstract truncation, concurrency 16

| abstract chars | prompt tokens | rows/s | p50 | p95 | 10,000 papers |
| --- | --- | --- | --- | --- | --- |
| 2000 | 408 | 6.41 | 2.47s | 2.76s | 26 min |
| 1000 | 351 | 7.78 | 2.02s | 2.20s | 21 min |
| 500 | 256 | 9.28 | 1.70s | 1.86s | 18 min |
| 250 | 205 | 11.71 | 1.34s | 1.55s | 14 min |

Sustained prefill is 2,400 to 2,700 prompt tokens per second in every configuration.
Completions are 13 tokens, so there is almost no decode for the batch to overlap.

Full run: 9,984 of 10,000 graded in 26.0 minutes, zero empty completions, zero parse failures,
zero errors.

## Reranking, 9,984 graded

| ranker | R@1000 | R@500 | R@200 |
| --- | --- | --- | --- |
| graph order, unchanged | 0.647 | 0.412 | 0.213 |
| graph x norm(relevance) | 0.603 | 0.441 | 0.228 |
| llm relevance alone | 0.544 | 0.382 | 0.184 |
| llm relevance, graph tiebreak | 0.544 | 0.382 | 0.184 |

## Grade against citation, 9,984 graded

| relevance | papers | references | reference rate |
| --- | --- | --- | --- |
| 2 | 332 | 31 | 9.34% |
| 1 | 1,662 | 50 | 3.01% |
| 0 | 3,728 | 23 | 0.62% |
| -1 | 2,095 | 13 | 0.62% |
| -2 | 2,167 | 10 | 0.46% |

| quantity | value |
| --- | --- |
| graded relevance >= 1 | 1,994 (20.0%) |
| of those, cited by the survey | 81 (4.1%) |
| references present in the graded set | 127 of 136 |

## Files

```
fetch.py     pulls the top 10,000 by the tuned graph ranking, with abstracts
grade.py     the grader and the throughput harness
run_full.py  the 10,000-paper run
eval.py      grades against citation, and the reranking comparison
papers.json  the candidates
grades.json  arxiv_id to relevance
full.log     the run
```
