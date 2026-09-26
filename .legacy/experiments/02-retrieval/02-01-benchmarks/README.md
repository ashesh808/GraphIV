# 02-01-benchmarks

**What:** compared to an existing benchmark, how does GraphIV do, and does their task transfer.
Six sections.
No model runs here: every arm was scored once and this reads the cached scores.

**Conclusion:** on their task our reader rerank beats GritLM-7B.
On our task their flat retrievers get 172 papers where we get 341.
The graph signal is the best part of our method on our task and the worst signal on theirs.
They are two different jobs sharing one name.

Run: `uv run python run.py` (reads `cache/`, writes `results/`, a few seconds).

## 1. Reproduce their number

Their BM25, their corpus, their queries, their metric, our harness.

| cell | published | ours |
| --- | --- | --- |
| specific R@5 | 50.0 | 50.0 |
| broad R@20 | 39.9 | 39.9 |

Exact.
This is the point of the section.
Any later difference is the method, not our code.

It only matches if the index is built their way: the key is the document text, so their 64183 rows
collapse to 57657 distinct keys.
Skip that and the number moves.

## 2 + 3. Run our methods on their task

| system | specific R@5 | broad R@20 | source |
| --- | --- | --- | --- |
| ours, graph only | 14.8 | 39.2 | measured |
| ours, joint | 26.7 | 42.7 | measured |
| GTR-T5-large | 39.6 | 43.8 | published |
| BM25 | 50.0 | 39.9 | published |
| Instructor-XL | 52.3 | 56.5 | published |
| E5-large-v2 | 56.2 | 55.4 | published |
| **ours, dense only** | **62.6** | **59.2** | measured |
| GPT-4 rerank over BM25 | 68.0 | 59.9 | published |
| GritLM-7B | 74.8 | 70.8 | published |
| **ours, reader rerank** | **75.8** | **74.7** | measured |
| GPT-4 rerank over GritLM | 79.2 | 75.3 | published |

Two results.
Our reader rerank beats GritLM-7B and beats GPT-4 reranking over BM25, on one local 26B model.
Our graph signal is dead last, and blending it in at the weight tuned on our own task costs 36
points against plain dense.

Caveat: our reranker sits on our own dense top 100, while the GPT-4 rows sit on BM25 or GritLM top
100, so no published row differs from us in exactly one component.

## 4. Define our own task

| task | questions | mean answers | one-answer share | key written by |
| --- | --- | --- | --- | --- |
| find this paper (LitSearch) | 597 | 1.07 | 94% | the citing author |
| cover this field (ours) | 60 | 26.9 | 0% | the survey author |

LitSearch asks for one paper and 94 percent of its questions have exactly one right answer.
Ours asks for a field and never has fewer than a handful.
Same words, different job.

### How the 60 surveys were picked

| stage | surveys |
| --- | --- |
| title regex, 60+ refs, 20+ cites, 2022-2024 | 1003 |
| sampled for the abstract screen | 140 |
| screen says it is a real review | 122 |
| kept, spread over 17 archives | 60 |
| held out, never tuned on | 30 |

The screen matters.
The title keyword pulls in astronomy sky surveys and telescope papers, which are not literature
reviews, and reading the abstract throws those out.

Each survey then gets a question written from its abstract, the corpus frozen at its publication
month, and itself blocked from its own results.

### Why the key is mention count and not citation intent

| arm | papers | median background % |
| --- | --- | --- |
| survey | 20 | 93.0 |
| ordinary paper (control) | 40 | 88.9 |

Survey references are 93 percent background, which looks like a finding until ordinary papers with
the same categories and reference counts come back at 89 percent with the gradient flat in both.
So intent does not separate a reference that matters from one that does not.
How often a survey mentions a paper does, and the key is filtered to three or more mentions.

## 5. Run both method families on our task

30 held-out surveys, 788 gold papers, 80 slots each.

| selector | graph | reader | gold found |
| --- | --- | --- | --- |
| lexical only | no | no | 54 |
| RRF of both | no | no | 137 |
| dense only | no | no | 172 |
| ours, ppr | yes | yes | 277 |
| ours, frontier | yes | yes | 320 |
| **ours, joint** | yes | yes | **341** |

Read the ceilings before reading the gap.
The flat arms can reach all 788.
Ours builds a pool first and then selects, so it can only reach the 441 that made it into the pool.
Our selector wins while handicapped, but the ceilings are not the same and the raw gap overstates it.

RRF is worse than dense alone because the lexical arm is noisy on long questions.

### Why their methods do not translate

Flat dense retrieval has no way to reach a paper that does not look like the question.
A survey's references include foundations written before the vocabulary existed.
The citation graph reaches those; embedding similarity does not.

### Why ours does not translate either

Their task has one right answer.
Our graph term ranks by citations per year, so it pushes well-cited papers up.
When there is exactly one target, that buries it under its famous neighbours.
14.8 against 62.6 for plain dense is that effect at full strength.

## 6. Conclusion

The citation graph is not generally good or generally bad.
It pays when the answer is a set and the set includes old work.
It costs when the answer is one specific paper.

Any system that claims one number for "literature search" is measuring one of these two jobs and
quietly assuming the other behaves the same.
It does not.
