# 02-06-leyline

**What:** LeyLine contributes 8 of the 80 landmark slots, so a whole-list score dilutes it ten to
one.
This isolates those 8 picks and scores them against the PPR slots they displace, then opens the two
limits on the walk to see whether either is holding it back.

**Conclusion:** the quota earns its slots.
Its picks hit gold 1.7 times as often as the slots they take, at less than half the age.
Both limits are load-bearing: every way of opening them makes the picks younger and worse.

Run: `uv run python run.py` (reads `cache/leyline.json`, a few seconds).

## What the walk does

`_adjacency` maps cited to citing, so the walk runs forward in time.
It picks an ancestor that can reach a lot of high-relevance mass, then follows one thread toward the
present, and the thread ends at the newest work on that lineage.

Two limits fall out of the implementation.
Only papers graded relevance 2 or higher become magnets, and only magnets can be collected off a
thread.
So LeyLine reorders the reader-vouched set by lineage position; it never discovers a paper the
reader graded lower.

## The quota isolated

| answer key | LeyLine's 8 picks | the slots they take | ratio | age |
| --- | --- | --- | --- | --- |
| 3+ mentions (suite standard) | **18.1%** | 10.4% | **1.73x** | 3.0 vs 7.0 |
| any mention | 41.8% | 29.8% | 1.40x | 3.0 vs 7.0 |

Both keys agree on direction.
The strict key is the suite standard and is the one to quote; the loose key is carried because the
earlier write-up used it without saying so.

LeyLine looks better under the stricter key, which is the useful direction: the papers it finds are
not just cited, they are cited repeatedly.

For scale, the magnet set and the whole pool both sit at a median age of 4 years.
LeyLine's picks are 3 and the slots they displace are 7, so the quota is not simply sampling
whatever is young.

## Opening the two limits

| arm | picks | gold hit | median age | dev | test |
| --- | --- | --- | --- | --- | --- |
| the PPR slots the quota takes | 480 | 10.4% | 7.0 | 235 | 246 |
| **shipped (rel>=2, magnets only)** | 421 | **18.1%** | 3.0 | **247** | 260 |
| rel>=2, any node on thread | 453 | 16.1% | 3.0 | 245 | 259 |
| rel>=1, magnets only | 480 | 14.8% | 2.0 | 242 | 260 |
| rel>=1, any node on thread | 480 | 12.7% | 2.0 | 236 | 256 |
| rel>=0, any node on thread | 480 | 12.1% | 2.0 | 239 | 250 |
| rel>=0, magnets only | 480 | 11.5% | 2.0 | 234 | 252 |

Both knobs degrade monotonically when opened.
Dropping the magnet floor to relevance 1 costs 3.3 points of gold hit, dropping it to 0 costs 6.6.
Letting the walk collect any node it passes rather than only magnets costs 2.0.
Opening both costs 6.0 and lands at 12.1 percent, barely above the unfiltered PPR slots.

Every relaxation also makes the picks younger, from a median of 3 years to 2.
So the floor is not limiting how far forward the walk reaches.
It is a quality gate, and removing it lets the walk wander into whatever is adjacent and new.

That is the trend-chasing failure mode in miniature, which is the objection any recency-seeking
method has to answer.

## What this does not settle

The instrument is a survey reference list, which is retrospective by construction and biased
against exactly the recent work LeyLine is built to find.
The effect here is large and monotone and the full-list counts move with it, so the bias does not
explain it away.
But the fair test is a forward-looking answer key, which is 02-08.
