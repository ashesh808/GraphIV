# Can we compare GraphIV against LitSearch and PaSa

## Verdict

1) Direction A on LitSearch is possible on 503 of 597 queries, but only as a known-item search
   task, because 563 of the 597 queries have exactly one gold paper.
2) Direction A on PaSa is blocked today, since `CarlanLark/pasa-dataset` is gated and no token
   exists on this machine, and no mirror or fork carries the data.
3) PaSa is nonetheless the better protocol match in every respect that matters, so obtaining a
   token is the single highest-value action on this list.
4) Direction B is possible for all five LitSearch retrievers, which are public checkpoints over
   a plain cosine index, and impossible for PaSa's full agent, whose `[Search]` tool is Google.
5) A naive side-by-side of any GraphIV number against a published one is wrong, because the
   corpus is 48x larger, the gold sets are 100x smaller, and no date control exists on LitSearch.

## Coverage, LitSearch

Gold papers, by whether they reach an arXiv id that `paper_meta` holds:

| step | count | of 574 |
| --- | --- | --- |
| distinct gold papers in the benchmark | 574 | 100.0% |
| resolved by the Semantic Scholar batch API | 572 | 99.7% |
| carrying an arXiv id | 458 | 79.8% |
| those arXiv ids present in our corpus | 458 | 79.8% |
| recovered by exact normalized-title match | +5 | +0.9% |
| **mappable into our corpus** | **463** | **80.7%** |

**458 of 574 LitSearch gold papers map to arXiv ids present in our corpus, rising to 463 of 574
once exact title matching is added.**
Every one of the 456 distinct arXiv ids resolved is in `paper_meta`, so nothing is lost at our
end: the entire shortfall is that 114 gold papers were never posted to arXiv.

Where the 114 unreachable gold papers were published:

| venue | count |
| --- | --- |
| ACL | 49 |
| NAACL | 10 |
| Findings | 9 |
| EMNLP | 7 |
| SemEval | 5 |
| other, 12 venues | 34 |

Queries, by whether at least one gold paper survives:

| slice | total | usable | lost | kept |
| --- | --- | --- | --- | --- |
| all | 597 | 503 | 94 | 84.3% |
| broad, `specificity=0`, reported at R@20 | 155 | 134 | 21 | 86.5% |
| specific, `specificity=1`, reported at R@5 | 442 | 369 | 73 | 83.5% |
| `inline_acl` | 98 | 71 | 27 | 72.4% |
| `inline_nonacl` | 253 | 216 | 37 | 85.4% |
| `manual_acl` | 155 | 125 | 30 | 80.6% |
| `manual_iclr` | 91 | 91 | 0 | 100.0% |

493 queries keep all their gold papers, 10 keep some, 94 keep none.
526 of 639 gold mentions survive, 82.3%.

The loss is structural and not random.
`manual_iclr` survives intact because ICLR submissions are on arXiv, while `inline_acl` loses
27.6% because ACL Anthology papers frequently are not.
The paper reports in its Table 6 that ACL-sourced and non-ACL-sourced questions behave
differently, so dropping the unmappable queries shifts the subset mix that number was measured
on.

## Coverage, PaSa

The dataset could not be downloaded.
Every unauthenticated request returns HTTP 401 with `Access to dataset CarlanLark/pasa-dataset
is restricted`, and the same holds through `hf-mirror.com` and the HF datasets-server.
The first 100 of the 122 GitHub forks of `bytedance/pasa` all report upstream's own 1520 KB
size, so none of them vendored the data.
No mirror of AutoScholarQuery or RealScholarQuery exists on HuggingFace.
`pasa_mapped.jsonl` therefore does not exist, and `map_pasa.py` will build it in one run once
`hf auth login` has been done and the dataset terms accepted, which is auto-approved.

What can be said without the data:

| fact | value | source |
| --- | --- | --- |
| gold identifier | arXiv id, by construction | paper 3.1 |
| gold papers filtered to | those retrievable on arXiv | paper 3.1 |
| our corpus size | 3,100,419 arXiv papers | measured |
| our newest paper | 2026-07 | measured |
| latest PaSa query date | 2024-10-01 | paper 3.2 |
| published example gold titles found in our corpus | 15 of 15 | measured |

AutoScholarQuery's gold papers are arXiv ids that were on arXiv before 2024-10, and our corpus
is a full arXiv snapshot running through 2026-07, so coverage should be near total rather than
the 80.7% LitSearch allows.
The 15 of 15 hit rate on the answer titles printed in the paper's Table 1 and Table 12 is
consistent with that, but 15 is not a coverage measurement and must not be quoted as one.

## The mismatches that make a naive comparison wrong

### Gold-set size

| benchmark | mean | median | min | max |
| --- | --- | --- | --- | --- |
| LitSearch, all | 1.07 | 1 | 1 | 5 |
| LitSearch, broad subset | 1.17 | 1 | 1 | 5 |
| LitSearch, specific subset | 1.04 | 1 | 1 | 4 |
| AutoScholarQuery | 2.16 to 2.94 by conference | 2 | not reported | not reported |
| GraphIV survey-qrels battery | 144.0 | 113 | 60 | 471 |

The GraphIV battery's gold set is 134x larger at the mean than LitSearch's.
Recall at 5 against a single gold paper is a binary hit or miss on one document.
Recall at 5 against 113 gold papers is capped at 0.044 before any retrieval happens.
The two numbers are not the same quantity and cannot share an axis.

LitSearch's broad subset is the sharper trap.
Its annotation rubric called a question "broad" when roughly 20 papers would answer it, yet the
labelled gold set averages 1.17 papers, because the gold set is the papers cited at that one
citation mention and not the set of relevant papers.
A system that returns the other 19 relevant papers is neither rewarded nor punished.

### Corpus scope

| corpus | papers | ratio to LitSearch |
| --- | --- | --- |
| LitSearch retrieval corpus | 64,183 | 1.0x |
| our corpus, cs only, arXiv id <= 2407 | 524,629 | 8.2x |
| our corpus, cs only | 791,358 | 12.3x |
| our corpus, all | 3,100,419 | 48.3x |

LitSearch's corpus is 59,383 ACL Anthology plus 4,807 ICLR papers, restricted for efficiency.
449 of our 456 mapped gold papers are in the `cs` archive, so LitSearch is a pure ML and NLP
benchmark, while the GraphIV battery is 9 of 60 `cs` with the rest in physics, `eess` and
`quant-ph`.
Running GraphIV over our whole corpus against a LitSearch gold paper is a strictly harder task
than the one their table measures, and the LitSearch authors already flag exactly this when
they caveat their own Table 7 as "not apples-to-apples as search engines use a much larger
retrieval corpus".

The intersection cannot be used as a clean restricted corpus either.

| slice of the LitSearch corpus | docs | share |
| --- | --- | --- |
| all documents | 64,183 | 100.0% |
| carrying an arXiv id | 16,811 | 26.2% |
| distinct arXiv ids among them | 16,693 | |
| those ids present in `paper_meta` | 16,693 | 100.0% |

Every arXiv id LitSearch's corpus contains is in our corpus, so our arXiv coverage is not the
limit: 73.8% of their corpus was simply never posted to arXiv.
Restricting retrieval to the 16,693-document intersection would make the haystack comparable but
would delete three quarters of the competing papers that make their task hard, which lowers the
task's difficulty rather than matching it.

### Date cutoff and leakage

| benchmark | per-query date | enforced how |
| --- | --- | --- |
| LitSearch | **absent from the dataset** | nothing |
| AutoScholarQuery | source paper publication date | search restricted with `before:` |
| RealScholarQuery | 2024-10-01 for all 50 | same |
| GraphIV battery | survey's `YYMM` | `--set-max-date`, plus `--set-exclude` for the survey |

The task brief assumed they do not freeze the corpus at the query date.
PaSa does, at day granularity, and its runner backs the cutoff off by a further 7 days so a
gold paper cannot be reached through the source paper itself.
LitSearch does not, and worse, it cannot be made to: the released query set carries only
`query_set`, `query`, `specificity`, `quality` and `corpusids`, with no source paper and no
date, so no per-query cutoff can be reconstructed.

The exposure this creates runs the other way from the usual worry.
Our corpus holds 566,123 papers published after LitSearch's own release month, none of which
any LitSearch baseline ever had to rank against.
Those are pure distractors that depress our number, not leakage that inflates it.
The newest LitSearch gold paper is from 2023, so a global `--set-max-date 2312` is defensible
and would remove them, at the cost of no longer being the protocol either side actually ran.

### Identifier and matching

| benchmark | identifier | failure mode |
| --- | --- | --- |
| LitSearch | S2 corpusid | 19.9% of gold papers have no arXiv version at all |
| PaSa | arXiv id in the data, normalized title in the scorer | a retitled arXiv version silently misses |

PaSa's `metrics.py` compares `keep_letters(title)`, which is the lowercased letters-only title,
not the arXiv id the dataset stores.
Our own bridge validated at 452 of 458 gold papers agreeing with the S2 title on the first 40
characters, and the 6 disagreements are arXiv preprint titles that changed before publication,
which is the exact case that would silently miss under PaSa's scorer.

## Direction B, cost of running their retrievers on our benchmark

| quantity | value |
| --- | --- |
| documents to index | 3,100,419 |
| mean title + abstract length | 1,079 chars |
| total text | 3,190 MB |
| LitSearch's index size | 64,183 documents |

Their `kv_store` holds every document vector in one dense float16 matrix and scores a query by
`cosine_similarity` against all of it.
At float16 that is 4.8 GB for a 768-dim encoder, 6.4 GB at 1024 dims and 25.4 GB for GritLM's
4096, with a full scan of it on every query, so their code does not transfer to our corpus
unchanged and needs an ANN index behind it.
Our pgvector HNSW already serves exactly that shape, so the port is to keep their encoder and
their prompts and replace their scorer, which changes nothing they measured.

BM25 is the harder port, not the easier one: `rank_bm25.BM25Okapi` is pure Python and holds the
full posting structure in memory, so it will not take 3.1M documents.
Their analyzer chain must be reproduced exactly, NLTK tokenizer then NLTK English stopwords then
Porter stemmer, on top of a different index implementation.

GritLM-7B encoding 3.1M documents is the largest single cost and is a one-off GPU job.

## What to do

1) Ask the user to run `hf auth login` and accept the CarlanLark/pasa-dataset terms, then run
   `map_pasa.py`, since PaSa matches our protocol on identifier, date control and gold-set size.
2) Report LitSearch as a 503-query subset with the kept fraction printed per `query_set`, never
   as "LitSearch", and never in the same column as the paper's 597-query numbers.
3) For direction B, run BM25, GTR, E5 and Instructor over our own corpus and battery, which is
   an exact reimplementation and the only fully clean comparison available in either direction.
4) Treat any GPT-4-reranked or Google-based arm as unreproducible and quote it only from the
   paper, with the protocol printed beside it.
5) Do not restrict our corpus to the 16,693-document intersection to make the haystacks match,
   since that removes the distractors rather than the mismatch.
