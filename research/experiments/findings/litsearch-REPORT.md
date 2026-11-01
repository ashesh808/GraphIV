# litsearch

LitSearch `2407.18940` run against our corpus, as an external calibration of the retrieval
backbone.

## Protocol

| item | LitSearch paper | this run |
| --- | --- | --- |
| queries | 597 | 474, those whose every target exists in our corpus |
| targets per query | 1 median, 5 max | same |
| corpus | 64,183 S2ORC papers | three settings, below |
| retriever | GritLM and others | nomic-embed-text-v2-moe, off the shelf, cosine only |
| metric | recall@5, recall@20 | same |
| target mapping | | LitSearch title to our title, normalized |

Of the 64,183 LitSearch corpus papers, 13,760 matched a paper in our corpus by title.
474 of 597 queries (79.4%) have all their targets among those.

## Results

| setting | corpus | R@5 | R@20 |
| --- | --- | --- | --- |
| ours, full corpus | 3,103,758 | 0.379 | 0.549 |
| ours, matched corpus size | 64,183 | 0.619 | 0.743 |
| ours, mapped LitSearch papers only | 13,760 | 0.679 | 0.776 |
| GritLM, published | 64,183 | | 0.708 |
| GritLM plus LLM reranking, published | 64,183 | | +4.4% relative |

The matched setting holds 13,760 LitSearch papers plus 50,423 arXiv papers dated 2015 or later,
drawn by `md5(arxiv_id)` order, to reach exactly 64,183.

## What blocks a clean comparison

1. The distractors differ. Ours are drawn from all of arXiv, so they span physics, mathematics
   and biology, while the LitSearch corpus is a curated set of topically adjacent papers. Ours
   is the easier corpus at the same size.
2. 123 of 597 queries are excluded because their targets are not in our corpus at all.
3. Targets are mapped by normalized title, which can mismatch.

The number is indicative. It is not evidence of beating GritLM.

## Cost

| setting | seconds per query |
| --- | --- |
| full corpus, HNSW index | 0.15 |
| restricted by an id list | 0.28 |

No LLM in the loop, no GPU beyond the embedding endpoint.

## Not tested

The ancestor and frontier channels were not run here, only cosine. LitSearch asks a specific
question with one correct answer, where those channels have no cohort to work with.

## Files

```
fetch.py     downloads LitSearch and maps its corpus onto ours by title
run.py       full corpus and mapped-papers-only settings
matched.py   the 64,183 matched corpus size setting
litsearch.json, results.json
```
