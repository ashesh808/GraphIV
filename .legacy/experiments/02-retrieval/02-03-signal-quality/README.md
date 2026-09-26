# 02-03-signal-quality

**What:** the pool already holds the right papers.
Which signal tells you which ones they are.
Four signals scored against the survey's own reference list, over the 60 frozen pools.
No LLM: the grades were cached once and this reads them.

**Conclusion:** the citation graph and the reader are equally good, 597 papers against 596, and
they disagree about which ones.
Each finds roughly a fifth of the gold the other cannot see.
That is why a selector should use both, and it is measured here rather than assumed.

Run: `uv run python run.py` (reads `cache/signal_quality.json`, a few seconds).

## What predicts gold

19976 pool papers, 860 of them gold, 4800 landmark slots, base rate 4.3 percent.

| signal | gold found | precision | lift | before the score fix |
| --- | --- | --- | --- | --- |
| citations per year | 597 | 12.4% | **2.9x** | 597 |
| reader relevance | 596 | 12.4% | **2.9x** | 596 |
| in-degree | 475 | 9.9% | 2.3x | 475 |
| text similarity | 399 | 8.3% | 1.9x | 330 |

Three things fall out.

The graph and the reader are a dead tie.
Neither is the senior partner, which is not what the old 27-topic version of this experiment
implied.

Age normalisation is what makes the graph competitive.
Raw in-degree is 2.3x, citations per year is 2.9x, and the only difference is dividing by age.

Text similarity is the weakest of the four.
It is the signal the query itself produces, and it predicts a survey's references worse than either
the citation structure or a reader who looked at the abstract.

## Why the selector needs both

| found by | gold papers | share |
| --- | --- | --- |
| both | 437 | 50.8% |
| graph only | 160 | 18.6% |
| reader only | 159 | 18.5% |
| neither | 104 | 12.1% |
| **either one** | **756** | **87.9%** |

160 against 159 is as symmetric as this gets.
Either signal alone reaches about 597 papers, and the two together reach 756.

That gap is the entire case for a fused selector, and Act III spends it.

## A bug found on the way, and shipped fixed

The pool's score field used to carry two different scales at once.

| scale | papers | share of pool | gold rate | mean reader relevance |
| --- | --- | --- | --- | --- |
| RRF rank (hybrid survivors) | 4144 | 20.7% | **5.7%** | **1.03** |
| cosine (every later stage) | 15832 | 79.3% | 3.9% | 0.47 |

`hybrid_pool` fused the vector and lexical channels by reciprocal rank and left that rank as the
node score.
`refined_pool` kept those survivors untouched and every later stage wrote a real cosine, so a fifth
of each pool sat about a hundred times too low.

Those were the better papers.
Higher gold rate, more than double the mean reader relevance, because they are the ones the query
itself matched rather than the ones the graph pulled in by association.

It showed in the decile profile.
Every other signal decays from the top down; the old text-similarity profile turned back up at the
bottom, which was the buried fifth showing through.

```
before   9.5%  4.5%  3.2%  3.3%  3.4%  3.7%  2.9%  3.6%  4.4%  4.3%
after   10.0%  6.8%  4.9%  3.9%  3.8%  2.5%  2.9%  2.6%  3.1%  2.4%
```

**Shipped:** `hybrid_pool` still selects by RRF and now writes a cosine, so the whole pool is on one
scale.
Worth 69 papers to this signal (330 to 399), 16 to ppr and 11 to trajectory, since both seed off
the score.
It is worth nothing to the joint selector, which never reads it.

## For the arc

Two signals, equally strong, largely disagreeing.
The next question is how to spend a fixed budget across both, which is 02-04 onward.
