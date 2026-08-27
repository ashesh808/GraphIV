# LitSearch and PaSa, evaluation protocols

Sources are marked per row: `paper` is the arXiv HTML in our own store, `repo` is the GitHub
checkout under `raw/`, `hf` is the HuggingFace dataset card, `measured` is computed here.

## Provenance of every file under `raw/`

| file | origin | note |
| --- | --- | --- |
| `raw/litsearch/query-full-00000-of-00001.parquet` | `hf princeton-nlp/LitSearch`, config `query` | 597 rows, complete |
| `raw/litsearch/queries.jsonl` | derived from the parquet | same 597 rows |
| `raw/litsearch/corpus_clean_ids_titles.parquet` | `hf` config `corpus_clean`, columns `corpusid,title,citations` | 64183 rows, `full_paper` and `abstract` columns not pulled |
| `raw/litsearch/gold_corpusids.txt` | derived | 574 unique gold corpusids |
| `raw/litsearch/s2_corpusid_map.json` | Semantic Scholar `graph/v1/paper/batch` | 572 of 574 resolved |
| `raw/litsearch/s2_corpus_map.jsonl` | Semantic Scholar `graph/v1/paper/batch` | all 64183 corpus docs, 16811 carry an arXiv id |
| `raw/litsearch/code_*.py` | `repo princeton-nlp/LitSearch@main` | full eval tree |
| `raw/pasa/code_*` | `repo bytedance/pasa@main` | full repo except images |
| AutoScholarQuery, RealScholarQuery | **not obtained** | see the gating row below |

`CarlanLark/pasa-dataset` is `gated: auto` and every unauthenticated fetch returns HTTP 401
with the body `Access to dataset CarlanLark/pasa-dataset is restricted.`
The same 401 comes back from `hf-mirror.com` and from the HF datasets-server.
No token exists on this machine, the first 100 of 122 forks of `bytedance/pasa` all report
upstream's own 1520 KB size, and no HF mirror of AutoScholarQuery or RealScholarQuery exists.
Everything below about PaSa therefore comes from the paper and the eval code, not from the data.

## What one query is

| | LitSearch | AutoScholarQuery | RealScholarQuery |
| --- | --- | --- | --- |
| count | 597 | 33551 / 1000 / 1000 train/dev/test | 50 |
| written by | GPT-4 from a citing paragraph, or by the paper's own author | GPT-4o from a Related Work section | AI researchers using the live system |
| source venues | ACL Anthology, ICLR | ICLR 23, ICML 23, NeurIPS 23, ACL 24, CVPR 24 | none, real user queries |
| mean length | 141 chars (`measured`) | not reported | not reported |
| query date | absent | publication date of the source paper | 2024-10-01 for all 50 |
| subsets | `inline_acl` 98, `inline_nonacl` 253, `manual_acl` 155, `manual_iclr` 91 (`measured`) | by conference | none |
| extra labels | `specificity` 0/1, `quality` 1/2 | none | none |

LitSearch `specificity` 0 is "broad" (155 queries) and 1 is "specific" (442), which reproduces
the paper's Table 2 split of 155 broad and 442 specific (`measured` + `paper`).

## What the gold set is

| | LitSearch | AutoScholarQuery | RealScholarQuery |
| --- | --- | --- | --- |
| identifier | S2 `corpusid` (int) | arXiv id | paper title |
| gold set is | the papers cited at that citation mention | the Related Work references that exist on arXiv | pooled candidates kept by an annotator |
| mean size | 1.07 (`measured`) | 2.16 to 2.94 by conference (`paper` Table 2) | not reported |
| median size | 1 (`measured`) | 2 (`paper` Table 2) | not reported |
| 90th pct | 2 (`measured`) | 4 to 6 by conference (`paper` Table 2) | not reported |
| max size | 5 (`measured`) | not reported | not reported |

LitSearch gold-set size distribution, over all 597 queries (`measured`):

| gold papers | queries |
| --- | --- |
| 1 | 563 |
| 2 | 29 |
| 3 | 3 |
| 4 | 1 |
| 5 | 1 |

563 of 597 LitSearch queries have exactly one gold paper, so LitSearch is a known-item search
task rather than a coverage task.
639 gold mentions resolve to 574 distinct papers.

RealScholarQuery gold sets were built by pooling the output of PaSa, Google, Google Scholar,
ChatGPT and Google-with-GPT-4o, then having annotators keep the ones that answer the query
(`paper`, section 3.2).
Annotators reviewed 76 candidates per query on average (`paper`).

## What the corpus is

| | LitSearch | PaSa |
| --- | --- | --- |
| corpus | a fixed set of 64183 S2ORC documents | the live web, through Google |
| composition | 59383 ACL Anthology + 4807 ICLR, 7 in both (`paper` 2.5) | `site:arxiv.org` restricted Google, plus ar5iv for full text |
| indexed field | title + abstract by default, 134 words mean | title + abstract for the Selector, section text for the Crawler |
| closed set | yes | no |

LitSearch deliberately does not use the full S2ORC corpus, "for efficiency reasons" (`paper` 2.5).

## The official metric

| | LitSearch | PaSa |
| --- | --- | --- |
| definition | `len(set(retrieved) & set(gold)) / len(gold)` | `tp / (tp + fn)` where the sets are normalized titles |
| code | `utils/utils.py::calculate_recall` | `utils.py::cal_micro` driven by `metrics.py` |
| averaging | over queries | over queries |
| reported at | R@5 and R@20 for specific, R@20 for broad | R@20, R@50, R@100, plus unbounded recall and precision |
| denominator | the query's own gold set | the query's own gold set |
| matching | integer corpusid equality | `keep_letters(title)`, i.e. lowercase, letters only |

Both are a per-query recall averaged across queries, with the query's own gold set as the
denominator, so a query with one gold paper contributes 0.0 or 1.0 and nothing between.

PaSa's `recall@k` ranks the **Crawler's** collected papers by Selector score and cuts at k.
PaSa's unqualified `recall` and `precision` use the **Selector's** kept set, which has no size
limit, so precision and recall@k are not measured on the same set of papers.

LitSearch's repo has no script that prints recall.
`eval/retrieval/evaluate_index.py` writes the top-200 retrieved ids per query and stops, so the
published numbers come from `calculate_recall` applied outside the released code.

## Leakage control

| | control | source |
| --- | --- | --- |
| LitSearch | none, no query carries a date and the corpus is not filtered per query | `repo`, `measured` |
| AutoScholarQuery | only papers published before the query date count, and the query date is the source paper's publication date | `paper` 3.1 |
| PaSa at inference | Google is called with `before:{end_date}` and `site:arxiv.org` | `paper` 5.1, `repo utils.py::google_search_arxiv_id` |
| PaSa's `end_date` | source paper publication date **minus 7 days** | `repo run_paper_agent.py` |

The 7-day back-off is in the runner, not the paper, and it exists so a gold paper cannot be
found through the source paper itself.
GraphIV's `--set-max-date YYMM` plus `--set-exclude <ids>` is the same discipline at month
granularity.

## Numbers the papers report

LitSearch, title and abstract indexing, from Table 3 (`paper`):

| system | Avg broad R@20 | Avg specific R@5 |
| --- | --- | --- |
| BM25 | 39.9 | 50.0 |
| GTR-T5-large | 43.8 | 39.6 |
| Instructor-XL | 56.5 | 52.3 |
| E5-large-v2 | 55.4 | 56.2 |
| GritLM-7B | 70.8 | 74.8 |
| GPT-4 rerank over BM25 | 59.9 | 68.0 |
| GPT-4 one-hop over BM25 | 64.8 | 68.6 |
| GPT-4 rerank over GritLM | 75.3 | 79.2 |
| GPT-4 one-hop over GritLM | 73.2 | 77.0 |

LitSearch commercial engines, on a random 80-query subset of the specific questions, Table 7
(`paper`):

| system | inline R@5 | author R@5 |
| --- | --- | --- |
| BM25 | 38.5 | 62.6 |
| GritLM-7B | 67.7 | 82.5 |
| Google Search | 23.1 | 62.5 |
| Google Scholar | 20.5 | 17.5 |
| Elicit | 23.1 | 17.5 |

The paper attaches its own caveat to Table 7: "the comparison is not apples-to-apples as search
engines use a much larger retrieval corpus".

PaSa on the AutoScholarQuery test set, Table 5 (`paper`):

| system | crawler recall | precision | recall | R@100 | R@50 | R@20 |
| --- | --- | --- | --- | --- | --- | --- |
| Google | | | | 0.2015 | 0.1891 | 0.1568 |
| Google Scholar | | | | 0.1130 | 0.0970 | 0.0609 |
| Google with GPT-4o | | | | 0.2683 | 0.2450 | 0.1921 |
| ChatGPT | | 0.0507 | 0.3046 | | | |
| GPT-o1 | | 0.0413 | 0.1925 | | | |
| PaSa-GPT-4o | 0.7565 | 0.1457 | 0.3873 | | | |
| PaSa-7b | 0.7931 | 0.1448 | 0.4834 | 0.6947 | 0.6334 | 0.5301 |
| PaSa-7b-ensemble | 0.8265 | 0.1410 | 0.4985 | 0.7099 | 0.6386 | 0.5326 |

PaSa on RealScholarQuery, Table 6 (`paper`):

| system | crawler recall | precision | recall | R@100 | R@50 | R@20 |
| --- | --- | --- | --- | --- | --- | --- |
| Google | | | | 0.2535 | 0.2342 | 0.1834 |
| Google Scholar | | | | 0.2809 | 0.2155 | 0.1514 |
| Google with GPT-4o | | | | 0.2946 | 0.2573 | 0.2020 |
| ChatGPT | | 0.2280 | 0.2007 | | | |
| GPT-o1 | | 0.058 | 0.0134 | | | |
| PaSa-GPT-4o | 0.5494 | 0.4721 | 0.3075 | | | |
| PaSa-7b | 0.7071 | 0.5146 | 0.6111 | 0.6929 | 0.6563 | 0.5798 |
| PaSa-7b-ensemble | 0.7503 | 0.4938 | 0.6488 | 0.7281 | 0.6877 | 0.5986 |
