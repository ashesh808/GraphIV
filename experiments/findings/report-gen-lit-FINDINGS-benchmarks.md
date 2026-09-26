# Benchmarks for a citation-grounded literature review generator

Read on 2026-09-02 from local HTML except 2506.11763, which has a broken ar5iv conversion and was read
from `data/pdf/2506/2506.11763v1.pdf`.
Every repository and dataset URL below was probed with curl on 2026-09-02 and the HTTP status is stated.

## 1. SurGE (2508.15658)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one topic description, one generated survey | 2508.15658 sec 2 |
| retrieval metric | Recall@k of the ground-truth survey's own references | 2508.15658 sec 6.1 |
| generation metrics | Coverage (recall of references), Doc/Sec/Sent referencing accuracy, SQS, SHR, ROUGE-L, BLEU, Logic | 2508.15658 sec 4 |
| judged by | NLI cross-encoder `cross-encoder/nli-deberta-v3-base` for referencing accuracy, GPT-4o for SQS and Logic | 2508.15658 sec 4.2.1, 4.3, 4.4 |
| topics | 205 expert-vetted arXiv CS surveys published 2020 to 2024, each with 20 or more citations | 2508.15658 sec 3.1 |
| corpus | 1,086,992 arXiv papers, metadata only, no full text | 2508.15658 sec 3.3 |
| corpus provenance | seeded from the 205 surveys' references, expanded by arXiv search API keyword queries | 2508.15658 sec 3.3 |
| avg references per survey | 65.78 | 2508.15658 sec 3.4 |

Reported retrieval numbers (2508.15658 Table 1):

| system | R@20 | R@30 | R@100 | R@200 | R@500 | R@1000 |
| --- | --- | --- | --- | --- | --- | --- |
| BM25 | 0.0548 | 0.0652 | 0.1193 | 0.1596 | 0.2213 | 0.2715 |
| Paper Retriever (RoBERTa-base dual encoder, fine-tuned) | 0.1706 | 0.2145 | 0.3665 | 0.4681 | 0.6011 | 0.6805 |

Reported end-to-end numbers, all three baselines generating with Qwen2.5-14B-Instruct (2508.15658 Table 2, sec 5.5):

| baseline | Coverage | Doc-Rel | Sec-Rel | Sent-Rel | SQS | SHR | ROUGE-L | BLEU | Logic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RAG | 0.0214 | 0.2857 | 0.2502 | 0.2500 | 0.6829 | 0.7900 | 0.1519 | 10.38 | 4.6723 |
| AutoSurvey | 0.0351 | 0.3617 | 0.4935 | 0.4870 | 1.3902 | 0.9697 | 0.1578 | 10.44 | 4.7390 |
| StepSurvey | 0.0630 | 0.4576 | 0.4571 | 0.4636 | 1.1951 | 0.9763 | 0.1590 | 12.02 | 4.8451 |

1. Coverage is defined as recall of the ground-truth reference set, `|R_GT and R_G| / |R_GT|`, so a longer bibliography is not penalized (2508.15658 eq 1).
2. Referencing accuracy gives full credit for NLI "entailment", half credit for "neutral with entailment second", and zero otherwise, and any cited id absent from the 1.09M corpus is scored irrelevant at all three levels (2508.15658 sec 4.2.1, 4.2.3).
3. SQS is a GPT-4o holistic outline score from 1 to 5, and the reported values below 1.4 mean every baseline scores near the floor (2508.15658 sec 4.3, Table 2).
4. Data is public: the repo is at `https://github.com/oneal2000/SurGE` under MIT and returns HTTP 200, and the README points `data/surveys.json`, `data/corpus.json` and `data/queries.json` at a Google Drive folder that returns HTTP 200.
5. Running it needs no API key, no hidden test set and no submission server: `src/evaluator.py` uses `cross-encoder/nli-deberta-v3-base`, `BAAI/bge-large-en-v1.5` and BERTopic locally.
6. The one API dependency is SQS and Logic, which `src/evaluator.py` routes through an `openai.OpenAI` client whose `base_url` is settable, so a local OpenAI-compatible router can serve it, but then the judge is not GPT-4o and SQS and Logic stop being comparable to Table 2.
7. The published corpus schema is Title, Authors, Year, Date, Abstract, Category and `doc_id` with no arXiv id field, so joining SurGE `doc_id` to our `papers.arxiv_id` would have to go through normalized title matching (SurGE README data section).
8. The paper claims each corpus entry carries "a direct link to its arXiv page" (sec 3.3), which the released schema does not show, so treat the id join as unverified until the dump is downloaded.

## 2. SciReviewGen (2305.15186)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one chapter of a literature review | 2305.15186 sec 3.1 |
| task | query-focused multi-document summarization, cited papers given, not retrieved | 2305.15186 sec 1 |
| inputs | abstracts of the papers cited in that chapter, review title, chapter title | 2305.15186 sec 3.1 |
| metric | ROUGE-1, ROUGE-2, ROUGE-L, plus a three-way human preference study | 2305.15186 sec 5.1, 5.2 |
| judged by | automatic ROUGE with `use_stemmer=True`, and three graduate-level CS annotators | 2305.15186 sec 5.1, 5.2 |
| size, original version | 9,187 train / 484 valid / 459 test whole reviews | 2305.15186 Table 1 |
| size, split version | 84,705 train / 4,410 valid / 4,457 test chapters | 2305.15186 Table 1 |
| corpus | 10,269 CS literature reviews and 698,049 cited papers extracted from S2ORC | 2305.15186 sec 3.2 |

Reported numbers on the split version (2305.15186 Table 3):

| system | ROUGE-1 | ROUGE-2 | ROUGE-L |
| --- | --- | --- | --- |
| LEAD | 23.09 | 4.68 | 11.72 |
| LexRank | 24.40 | 5.02 | 12.52 |
| Ext-oracle | 29.43 | 10.13 | 14.88 |
| Big Bird (bigbird-pegasus-large-arxiv, fine-tuned) | 24.25 | 4.08 | 15.30 |
| FiD (BART-large-cnn init, fine-tuned) | 32.40 | 6.75 | 16.17 |
| QFiD (their model, 406M) | 34.00 | 7.75 | 16.52 |
| GPT-3 davinci, zero-shot | 9.77 | 1.25 | 8.67 |

Human evaluation, 30 chapters from five computer-vision reviews, QFiD against the ground truth (2305.15186 Table 4):

| criterion | ground truth better | comparable | generated better |
| --- | --- | --- | --- |
| Relevance | 25.6% | 56.7% | 17.8% |
| Coherence | 48.9% | 31.1% | 20.0% |
| Informativeness | 64.4% | 20.0% | 15.6% |
| Factuality | 40.0% | 48.9% | not stated separately, 60.0% comparable or better |
| Overall | 68.9% | 8.9% | 22.2% |

9. Inter-annotator agreement on the human study is Cohen's kappa 0.212 across three categories, which the authors call reasonable and which is weak evidence by any normal reading (2305.15186 sec 5.2).
10. Data is public: `https://github.com/tetsu9923/SciReviewGen` returns HTTP 200 and the README links three Google Drive files, of which `split_survey_df` returns HTTP 200, under CC BY-NC 4.0 inherited from S2ORC.
11. Running it needs no API key, no hidden test set and no submission server, since the metric is ROUGE against a held-out chapter.
12. The benchmark hands the model its reference list, so it measures summarization only and cannot score retrieval at all (2305.15186 sec 1).

## 3. DeepResearch Bench (2506.11763)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one PhD-level research task, one long-form report | 2506.11763 sec 2.2 |
| tasks | 100, of which 50 Chinese and 50 English, across 22 WebOrganizer topic domains | 2506.11763 sec 2.2 |
| task provenance | proportionally sampled from 44,019 deep-research queries filtered out of 96,147 real user queries, then written by PhD-level domain experts | 2506.11763 sec 2.1, 2.2 |
| corpus | none, the agent searches the live web | 2506.11763 sec 3.2 |
| report metric | RACE, four dimensions COMP, DEPTH, INST, READ, scored relative to a reference report | 2506.11763 sec 3.1 |
| citation metric | FACT, Citation Accuracy and Average Effective Citations per task | 2506.11763 sec 3.2, appendix E |
| judged by | Gemini-2.5-Pro for RACE and Gemini-2.5-Flash for FACT in the paper, GPT-5.5 and GPT-5.4-mini in the current repo | 2506.11763 sec 4.1, repo README news of 11 May 2026 |

Reported numbers, Deep Research Agents (2506.11763 Table 1):

| system | RACE overall | Comp | Depth | Inst | Read | C. Acc. | E. Cit. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gemini-2.5-Pro Deep Research | 48.88 | 48.53 | 48.50 | 49.18 | 49.44 | 81.44 | 111.21 |
| OpenAI Deep Research | 46.98 | 46.87 | 45.25 | 49.27 | 47.14 | 77.96 | 40.79 |
| Perplexity Deep Research | 42.25 | 40.69 | 39.39 | 46.40 | 44.28 | 90.24 | 31.26 |
| Grok Deeper Search | 40.24 | 37.97 | 35.37 | 46.30 | 44.05 | 83.59 | 8.15 |

Reported numbers, LLMs with search tools (2506.11763 Table 1):

| system | RACE overall | C. Acc. | E. Cit. |
| --- | --- | --- | --- |
| Claude-3.7-Sonnet w/Search | 40.67 | 93.68 | 32.48 |
| Perplexity-Sonar-Reasoning-Pro (high) | 40.22 | 39.36 | 8.35 |
| Perplexity-Sonar-Reasoning (high) | 40.18 | 48.67 | 11.34 |
| Perplexity-Sonar-Pro (high) | 38.93 | 78.66 | 14.74 |
| Gemini-2.5-Pro-Grounding | 35.12 | 81.81 | 32.88 |
| GPT-4o-Search-Preview (high) | 35.10 | 88.41 | 4.79 |
| Perplexity-Sonar (high) | 34.54 | 74.42 | 8.67 |
| GPT-4.1 w/Search (high) | 33.46 | 87.83 | 4.42 |
| Gemini-2.5-Flash-Grounding | 32.39 | 81.92 | 31.08 |
| GPT-4.1-mini w/Search (high) | 30.26 | 84.58 | 4.35 |
| GPT-4o-Mini-Search-Preview (high) | 31.55 | 84.98 | 4.95 |
| Claude-3.5-Sonnet w/Search | 28.48 | 94.04 | 9.78 |

Human-consistency numbers for the evaluator itself (2506.11763 Table 2):

| method | Pairwise agreement | Overall Pearson | Filtered avg Pearson | Filtered avg Spearman |
| --- | --- | --- | --- | --- |
| RACE full | 71.33 | 99.54 | 60.24 | 59.12 |
| Vanilla prompt | 58.89 | 98.89 | 40.30 | 43.75 |
| RACE, no reference report | 66.56 | 97.46 | 57.51 | 51.23 |
| human inter-agreement | 68.44 | not applicable | not applicable | not applicable |

13. RACE is relative, `S_int(target) / (S_int(target) + S_int(reference))`, so 50 means parity with the reference report and no system can exceed 100 (2506.11763 eq 3).
14. The reference reports were generated by Gemini-2.5-Pro Deep Research in April 2025, which is why that system scores 48.88 and not 50 (2506.11763 sec 4.1).
15. FACT resolves every cited URL through the Jina Reader API and asks a judge whether the page supports the statement, so a citation to a paper we hold locally still has to be fetched over the network (2506.11763 sec 3.2).
16. Gemini-2.5-Flash agreed with human "support" calls 96% of the time and with "not support" 92% of the time on 100 sampled statement-URL pairs (2506.11763 appendix C).
17. Data is public: `https://github.com/Ayanami0730/deep_research_bench` returns HTTP 200 under MIT, ships `data/prompt_data/query.jsonl` with the 100 tasks and `data/test_data/{raw,cleaned}_data/reference.jsonl` with the reference reports.
18. Running it does need API keys: the repo README lists an OpenRouter or OpenAI key for RACE and a separate Jina key for FACT, with defaults `openai/gpt-5.5` and `openai/gpt-5.4-mini`.
19. There is no hidden test set, but there is a submission server in practice: an official leaderboard entry requires emailing the maintainers a temporary key with GPT-5.5 access plus the raw articles (repo README, Submit to Leaderboard).
20. The evaluator changed under the paper's own numbers on 11 May 2026, so Table 1 values are legacy Gemini-2.5-Pro scores and the maintainers are re-running them, meaning any number we quote must name its judge.

## 4. LitLLMs, Are we there yet? (2412.15249)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one query paper abstract, retrieving its reference list and writing its related-work section | 2412.15249 sec 3.1, 5 |
| datasets | RollingEval-Aug and RollingEval-Dec, 1,000 arXiv papers each before filtering, 500 used for the re-ranking experiments | 2412.15249 sec 3.1, 3.4 |
| corpus | no fixed corpus, candidates come from live arXiv API, SERP Google, Semantic Scholar API and the SPECTER2 150M-document embedding base | 2412.15249 sec 3.1, 3.2 |
| retrieval metric | coverage in the top-100, then normalized recall and precision at k after re-ranking | 2412.15249 sec 3.2, 3.4 |
| generation metric | ROUGE-1/2/L, plan-adherence rate, citation coverage | 2412.15249 sec 5, 6 |
| judged by | automatic metrics only, no LLM judge and no human study | 2412.15249 sec 5, 6 |

Top-100 coverage of the ground-truth reference set by search backend (2412.15249 Table 1):

| search type | RollingEval-Aug | RollingEval-Dec |
| --- | --- | --- |
| arXiv API, single query | 0.65% | 1.41% |
| SERP Google, single query | 1.23% | 4.34% |
| Semantic Scholar API, single query | 3.93% | 4.76% |
| arXiv API, multiple queries | 2.75% | 1.92% |
| SERP Google, multiple queries | 6.80% | 5.04% |
| Semantic Scholar API, multiple queries | 6.07% | 5.09% |
| SPECTER2 | 8.3% | 6.8% |
| Semantic Scholar multiple queries plus SPECTER2 | 9.8% | 8.2% |

Related-work generation on Multi-XScience (2412.15249 Table 3):

| system | ROUGE-1 | ROUGE-2 | ROUGE-L |
| --- | --- | --- | --- |
| One-line extractive baseline | 26.869 | 4.469 | 14.386 |
| LexRank | 30.916 | 5.966 | 15.916 |
| TextRank | 31.439 | 5.817 | 16.398 |
| Hiersum | 29.861 | 5.029 | 16.429 |
| Pointer-Generator (their stated prior state of the art) | 33.947 | 6.754 | 18.203 |
| PRIMER, reproduced | 26.926 | 5.024 | 14.131 |
| LongT5 | 19.515 | 3.361 | 12.201 |
| FlanT5 | 21.959 | 3.992 | 12.778 |
| Galactica-1.3B | 18.461 | 4.562 | 9.894 |
| Falcon-180B | 22.876 | 2.818 | 12.087 |
| Llama 2-Chat 7B, no plan | 24.636 | 5.189 | 13.718 |
| GPT-3.5-turbo, per-cite 2nd stage | 24.359 | 5.594 | 12.859 |
| GPT-3.5-turbo, sentence by sentence | 31.654 | 6.442 | 15.577 |
| GPT-3.5-turbo, no plan | 29.696 | 7.325 | 14.562 |
| GPT-4, no plan | 33.213 | 7.609 | 15.798 |
| Llama 2-Chat 70B, prompted plan | 30.389 | 7.221 | 14.911 |
| GPT-3.5-turbo, prompted plan | 32.187 | 7.788 | 15.398 |
| GPT-4, prompted plan | 34.819 | 7.892 | 16.634 |
| Llama 2-Chat 70B, teacher-forced plan | 34.654 | 8.371 | 17.089 |
| GPT-3.5-turbo, teacher-forced plan | 35.042 | 8.423 | 17.136 |
| GPT-4, teacher-forced plan | 37.198 | 8.859 | 18.772 |

Related-work generation on RollingEval-Aug (2412.15249 Table 4):

| system | ROUGE-1 | ROUGE-2 | ROUGE-L |
| --- | --- | --- | --- |
| CodeLlama 34B-Instruct | 22.608 | 5.032 | 12.553 |
| CodeLlama 34B-Instruct, plan | 27.369 | 5.829 | 14.705 |
| Llama 2-Chat 7B | 23.276 | 5.104 | 12.583 |
| Llama 2-Chat 13B | 23.998 | 5.472 | 12.923 |
| Llama 2-Chat 70B | 23.769 | 5.619 | 12.745 |
| GPT-3.5-turbo, zero-shot | 25.112 | 6.118 | 13.171 |
| GPT-4, zero-shot | 29.289 | 6.479 | 15.048 |
| Llama 2-Chat 70B, plan | 30.919 | 7.079 | 15.991 |
| GPT-3.5-turbo, plan | 30.192 | 7.028 | 15.551 |
| GPT-4, plan | 33.044 | 7.352 | 17.624 |

Citation coverage, defined as the share of outputs whose citation count equals the ground truth's (2412.15249 Table 6):

| system | coverage | avg words |
| --- | --- | --- |
| Llama 2-Chat 70B, zero-shot | 59.31% | 284.65 |
| Llama 2-Chat 70B, plan | 82.62% | 191.45 |
| GPT-3.5-turbo, zero-shot | 63.11% | 293.69 |
| GPT-3.5-turbo, plan | 68.03% | 202.81 |
| GPT-4, zero-shot | 91.34% | 215.15 |
| GPT-4, plan | 98.52% | 125.10 |

21. GPT-4 zero-shot ranking is structurally unreliable, producing a complete ranked list only 55.1% of the time on Aug and 59.7% on Dec, with the rest incomplete or containing repeated values (2412.15249 Table 2).
22. Removing the attribution-verification step from their debate re-ranker significantly hurts both precision and normalized recall at k=40, with t-test p-values of 4.7e-4 and 1.9e-6 (2412.15249 sec 3.5).
23. RollingEval-Aug is 1,000 examples derived from about 6.2k S2ORC rows for August 2023, averaging 2 citations and a 95-word related-work target (2412.15249 appendix B).
24. Data is partly public: `https://github.com/LitLLM/litllms-for-literature-review-tmlr` returns HTTP 200 and `https://huggingface.co/datasets/shubhamagarwal92/RollingEval-Aug` returns HTTP 200, but no RollingEval-Dec dataset appears in a HuggingFace search for "RollingEval".
25. The arXiv version anonymizes its code link as bare `github.com`, so the repo above is an identification made from the author list and title, not a link the paper gives.
26. Running the generation half needs no API key, but reproducing the retrieval half needs a SERP API key and Semantic Scholar API access, since there is no frozen candidate pool (2412.15249 sec 3.1).

## 5. SurveyForge and SurveyBench (2503.04629, benchmark portion only)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one of 10 CS topics, one generated survey | 2503.04629 sec 3.3, 4.1 |
| size | about 100 human-written surveys over 10 topics, one designated highest-quality survey per topic | 2503.04629 sec 3.3, appendix A.2 |
| reference set size | 330 to 994 references per topic | 2503.04629 appendix A.2 |
| corpus used by the system, not by the benchmark | about 600,000 papers and 20,000 review articles, `gte-large-en-v1.5` embeddings | 2503.04629 appendix A.1 |
| metrics | SAM-R Input Coverage and Reference Coverage, SAM-O outline score 0 to 100, SAM-C structure, relevance, coverage 0 to 100 | 2503.04629 sec 3.3 |
| judged by | GPT-4o-2024-08-06 and Claude-3.5-sonnet-20241022 for SAM-O and SAM-C, pure set overlap for SAM-R | 2503.04629 sec 4.1 |
| curated by | a panel of 20 doctoral researchers | 2503.04629 appendix A.2 |

Reported numbers (2503.04629 Table 1 and Table 7):

| method | generator | Input Cov. | Reference Cov. | Outline | Structure | Relevance | Coverage | Content avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Human-written | not applicable | not reported | 0.6294 | 87.62 | not reported | not reported | not reported | not reported |
| AutoSurvey | Claude-3-Haiku | 0.1153 | 0.2341 | 82.18 | 72.83 | 76.44 | 72.35 | 73.87 |
| SurveyForge | Claude-3-Haiku | 0.2231 | 0.3960 | 86.85 | 73.82 | 79.62 | 75.59 | 76.34 |
| AutoSurvey | GPT-4o mini | 0.0665 | 0.2035 | 83.10 | 74.66 | 74.16 | 76.33 | 75.05 |
| SurveyForge | GPT-4o mini | 0.2018 | 0.4236 | 86.62 | 77.10 | 76.94 | 77.15 | 77.06 |
| SurveyForge | DeepSeek-v3 | 0.2554 | 0.4553 | 87.42 | 79.20 | 80.17 | 81.07 | 80.15 |

Win rates against AutoSurvey (2503.04629 Table 2):

| axis | AutoSurvey | SurveyForge |
| --- | --- | --- |
| outline, LLM score win rate | 27.00% | 73.00% |
| outline, LLM pairwise win rate | 25.00% | 75.00% |
| outline, human evaluation | 26.00% | 74.00% |
| content, LLM score win rate | 31.00% | 69.00% |
| content, human evaluation | 30.00% | 70.00% |

27. SAM-R is `|R_generated and R_bench| / |R_generated|`, which is precision of the bibliography, not recall, so citing fewer and safer papers raises the score (2503.04629 eq 4).
28. The shipped `test.py` confirms the direction, computing `matched / total_papers` where `total_papers` is the generated reference count after a date filter that drops any cited paper newer than the newest benchmark reference.
29. Cost is reported at under $0.50 per 64k-token survey, $0.37 with DeepSeek-v3 and $0.43 with GPT-4o-mini (2503.04629 sec 4.2, appendix A.5).
30. Data is public: `https://huggingface.co/datasets/U4R/SurveyBench` returns HTTP 200 and redirects to `InternScience/SurveyBench`, which ships `ref_bench/` with ten per-topic reference files, `human_written_ref/`, `generated_surveys_ref/`, `topics.txt` and `test.py`.
31. SAM-R needs no API key, no hidden test set and no submission server, and it works purely on arXiv ids, which joins directly to `papers.arxiv_id`.
32. SAM-O and SAM-C do need a judge; the paper used GPT-4o and Claude-3.5-sonnet, and substituting a local judge makes those two numbers incomparable to Table 1.
33. Only 10 topics means a per-topic difference of one paper moves the mean noticeably, so any claim on SurveyBench should report the per-topic spread and not just the mean.

## 6. Artificial Intelligence for Literature Reviews (2402.08565)

34. This is a PRISMA tool survey of 21 AI-assisted systematic-review tools plus 11 LLM-based writing tools, not a benchmark, and it reports no system scores of any kind (2402.08565 sec 1, 2.2, 4).
35. It states plainly that no standard datasets or evaluation frameworks for SLR tools exist and that existing evaluations are not comparable (2402.08565 sec 5.2).
36. Its one transferable contribution is metric choice: it argues for F2 over F1 in screening because recall matters more, and for Work Saved over Sampling and its normalized variant nWSS to compare screening across reviews of different prevalence (2402.08565 sec 5.2).
37. There is nothing here to run and no number to beat.

## 7. AI4Research (2507.01903)

38. This is a taxonomy survey of AI across comprehension, survey, discovery, writing and peer review, and its only quantitative table on survey generation is a verbatim reproduction of SurveyForge's SurveyBench numbers, attributed to Yan et al. (2507.01903 sec 4.2.3, Table 2).
39. Its value to us is the resource index in sec 9.2, which names the benchmarks in this space: AcademicBrowse, Cochrane, MSLR 2022, MS^2, OARelatedWork, OAG-Bench, SciReviewGen, BigSurvey, SurveySum, SurveyBench, AutoSurvey, SurveyX and SurveyEval.
40. SurveyEval is called out as the one offering a hierarchical title tree with hierarchical-consistency and citation-chapter-alignment metrics, which is the closest listed match to our compose-time structure (2507.01903 sec 9.2).
41. The companion index is at `https://github.com/LightChen233/Awesome-AI4Research` (2507.01903 sec 1).
42. There is nothing here to run and no original number to beat.

## 8. Rethinking Literature Search Evaluation (2605.29234)

| item | value | source |
| --- | --- | --- |
| unit of evaluation | one query paper's full text, retrieving its reference list | 2605.29234 sec 3 |
| benchmark | RollingEval-Jun25, 250 CS arXiv submissions from June 2025 with cleaned full text and bibliographies | 2605.29234 sec 3 |
| corpus | none frozen, live arXiv, OpenAlex and Semantic Scholar plus breadth-first citation-graph expansion | 2605.29234 sec 2 |
| metrics | precision and recall against the human reference list, Semantic Relevance 0 to 100 from an LLM judge, alpha-nDCG, and co-authorship hop distance | 2605.29234 sec 3, appendix D |
| judged by | GPT-OSS-120B served with vLLM, conditioned on the query paper's full text and the candidate's title and abstract | 2605.29234 sec 3 |

Precision and recall against the human reference list, in percent (2605.29234 Table 1):

| system | P@20 | P@100 | P@1k | R@20 | R@100 | R@1k |
| --- | --- | --- | --- | --- | --- | --- |
| No re-rank, no deep research | 0.1 | 0.1 | 0.0 | 0.0 | 0.3 | 1.9 |
| PaSa | 5.3 | 4.5 | 1.5 | 1.3 | 7.4 | 27.8 |
| ScholarQA | 5.7 | 4.0 | 1.2 | 7.7 | 13.5 | 31.0 |
| Debate | 9.6 | 4.5 | 1.5 | 5.1 | 12.2 | 39.9 |
| Debate plus Qwen3 | 14.7 | 6.6 | 1.7 | 8.1 | 18.1 | 46.2 |
| Qwen3 embeddings | 16.8 | 8.0 | 1.9 | 9.6 | 22.2 | 51.9 |

Diversity and judged relevance (2605.29234 Table 2):

| system | alpha-nDCG@10 | @100 | @1k | Sem.Rel@10 | @100 | @1k |
| --- | --- | --- | --- | --- | --- | --- |
| No re-rank, no deep research | 15.3 | 41.2 | 62.1 | 9.2 | 17.3 | 17.4 |
| Debate plus Qwen3 | 53.2 | 76.2 | 87.9 | 67.9 | 53.8 | 33.2 |
| Debate | 54.1 | 79.7 | 89.1 | 55.4 | 39.8 | 27.1 |
| Qwen3 embeddings | 47.6 | 65.3 | 77.8 | 67.1 | 57.6 | 47.9 |
| Human reference list | not applicable | not applicable | not applicable | 47.3 | 50.7 | 50.8 |

Judged relevance at matched list length, 9,204 human pairs against 9,173 pairs per system (2605.29234 Table 3):

| source | mean | share at or below 40 | share at or above 60 |
| --- | --- | --- | --- |
| Human | 51.2 | 48.6% | 51.4% |
| Qwen3 embeddings | 62.4 | 14.0% | 86.0% |
| Debate plus Qwen3 | 62.4 | 12.2% | 87.8% |
| Debate | 45.6 | 37.9% | 62.1% |
| No re-rank, no deep research | 17.3 | 97.7% | 2.3% |

Co-authorship hop distance at matched list length, OpenAlex graph (2605.29234 Table 4):

| source | d=0 | d=1 | d=2 | d=3 | d>=4 |
| --- | --- | --- | --- | --- | --- |
| Human | 5.13 | 7.02 | 41.43 | 29.13 | 17.28 |
| Qwen3 | 2.05 | 5.36 | 41.25 | 34.14 | 17.19 |
| Debate plus Qwen3 | 1.92 | 4.98 | 39.69 | 36.06 | 17.35 |
| Debate | 1.52 | 4.32 | 38.18 | 36.72 | 19.27 |
| No re-rank, no deep research | 0.09 | 2.65 | 36.87 | 40.17 | 20.22 |

43. Their headline "above 80% recall" is at k=10^4, while the tabulated recall at k=1000 is 51.9%, so quoting the abstract number without the k is misleading (2605.29234 sec 4, Table 1).
44. This paper is the direct external validation of our architecture: breadth-first citation-graph expansion off the seed set is what raises recall from under 20% to above 80%, which is the same mechanism as our citation-graph drill.
45. It also undercuts the reference-recall family of metrics we and SurGE both use, since only 51.4% of human citations clear a moderate-relevance bar against 86.0 to 87.8% for the strongest re-rankers.
46. The stated cause is partly citation collusion, with humans 2.5x more likely to cite a direct co-author (5.13% against 1.9 to 2.1%) and 1.6x within one hop (12.2% against 6.9 to 7.4%), and the gap closes by d=3 (2605.29234 sec 5).
47. Conditional relevance means for humans are flat across hop distance (56.1, 52.6, 51.2, 51.2, 50.9), so proximity does not predict relevance and collusion explains only part of the gap (2605.29234 sec 5).
48. Data is not yet public: the paper says "we will release RollingEval-Jun25" under CC-BY-4.0 with Apache-2.0 code, and a HuggingFace dataset search for "RollingEval" returns only `shubhamagarwal92/RollingEval-Aug`.
49. Once released it would need no paid API key, since the judge is GPT-OSS-120B under Apache 2.0 and the embedder is Qwen3-Embedding-8B under Apache 2.0, but it does need live OpenAlex and Semantic Scholar access to rebuild candidate pools.
50. Its limitation section states the benchmark is CS-only, arXiv-indexed-references-only, and that the co-authorship fetch caps each author at 1,000 works, biasing the reported collusion gap conservatively.

## 9. Cross-benchmark comparison

| benchmark | size | corpus | headline metric | best reported number and system | offline on our hardware |
| --- | --- | --- | --- | --- | --- |
| SurGE 2508.15658 | 205 surveys | 1,086,992 arXiv abstracts, shipped | reference Recall@1000 | 0.6805, fine-tuned RoBERTa dual encoder | yes for retrieval and for coverage, referencing accuracy, SHR, ROUGE, BLEU; SQS and Logic need an OpenAI-compatible judge |
| SurGE 2508.15658 | same | same | generated-survey Coverage | 0.0630, StepSurvey on Qwen2.5-14B-Instruct | same |
| SurveyBench 2503.04629 | 10 topics, about 100 surveys | 330 to 994 refs per topic, shipped | SAM-R Reference Coverage | 0.6294 human-written, 0.4553 SurveyForge with DeepSeek-v3 | yes for SAM-R, which is pure arXiv-id set overlap; SAM-O and SAM-C need a judge |
| SciReviewGen 2305.15186 | 4,457 test chapters | 698,049 cited-paper abstracts, shipped | ROUGE-L | 16.52, QFiD 406M | yes, entirely |
| DeepResearch Bench 2506.11763 | 100 tasks, 22 domains | live web, none shipped | RACE overall | 48.88, Gemini-2.5-Pro Deep Research | no, needs a frontier judge key plus a Jina key and live web |
| DeepResearch Bench 2506.11763 | same | same | FACT Citation Accuracy | 94.04, Claude-3.5-Sonnet w/Search | no, same |
| RollingEval-Aug 2412.15249 | 1,000 examples | live search APIs plus SPECTER2 | top-100 coverage | 9.8%, Semantic Scholar multi-query plus SPECTER2 | generation half yes, retrieval half no |
| RollingEval-Aug 2412.15249 | same | same | ROUGE-L on related work | 17.624, GPT-4 with plan | yes for the generation half |
| RollingEval-Jun25 2605.29234 | 250 papers | live arXiv, OpenAlex, S2 | Recall@1000 | 51.9%, Qwen3 embeddings with deep research | not yet, data unreleased as of 2026-09-02 |
| 2402.08565 | not a benchmark | not applicable | not applicable | none reported | not applicable |
| 2507.01903 | not a benchmark | not applicable | not applicable | reproduces SurveyBench only | not applicable |

## 10. Shortlist, ranked by protocol match rather than by winnability

51. First, SurGE 2508.15658, because it is the only one of the eight whose protocol is exactly ours end to end: a topic in, retrieval from a frozen 1M-paper arXiv corpus, then a cited survey out, scored on both halves with the same reference set.
52. SurGE also has the property we most need for a reliability claim, which is that a cited id absent from the corpus is scored irrelevant at all three referencing levels, making our mechanical corpus-verification guard directly measurable rather than asserted.
53. Its generation numbers are near the floor (best Coverage 0.0630, best Sent-Rel 0.4870 against a retrieval ceiling of 0.3665 at k=100), which means the interesting result is the gap between our retrieval and our final citation set, not the absolute score.
54. Second, SurveyBench from 2503.04629, because SAM-R runs offline on bare arXiv ids with no judge and no key, and it is the only benchmark here with a human-written ceiling on the same metric (0.6294), which lets us say where we sit relative to a person rather than only relative to another system.
55. SurveyBench is also small enough that ten deep runs at our current effort settings is a day of GPU time, not a week, so it can be a regression gate rather than a one-off.
56. Third, RollingEval-Jun25 from 2605.29234 if and when the data lands, because it is the only published protocol that measures the exact mechanism we built, citation-graph expansion off a seed, and it ships the counter-metric (LLM-judged Semantic Relevance at matched list length) that keeps reference recall honest.
57. Until it lands, 2605.29234's method is still worth adopting on our own SurveyMatch and FrontierMatch sets: report reference recall, judged relevance at matched length, and the co-authorship-distance diagnostic together, since we already hold the citation graph needed for the third.
58. DeepResearch Bench is the one to run last and only if a frontier key is available, because its 100 tasks are general-web research questions across 22 domains including travel and entertainment, which is not the corpus-grounded scientific task we build for.

## 11. Traps

59. SurveyBench SAM-R is a precision metric dressed as coverage, `|R_generated and R_bench| / |R_generated|`, so it rewards a short conservative bibliography and punishes any correct citation outside the ten curated reference lists; optimizing it would push us toward exactly the generic-hub dominance we already fixed with a compose guard.
60. SurveyBench's date filter compounds this, dropping every cited paper newer than the newest benchmark reference from the denominator only after it is excluded from the numerator, so a frontier-mode run that surfaces genuinely recent work is scored as if that work did not exist.
61. SurGE's Coverage is the opposite failure and is also gameable, since it is pure recall of the reference set with no precision term, so emitting a 600-paper bibliography raises it monotonically; report it beside a precision or a per-sentence support number or it means nothing.
62. SurGE's SQS is a GPT-4o holistic 1-to-5 score on which every published baseline lands between 0.68 and 1.39, which is the floor, so the metric has essentially no discriminative range and beating it proves nothing.
63. SciReviewGen's ROUGE-L is a lexical-overlap metric on a task where the reference list is handed to the model, so it measures paraphrase fidelity to one human's chapter and rewards nothing we care about; note that its own extractive oracle beats two of the neural systems on ROUGE-2 while FiD beats the oracle on ROUGE-1 and ROUGE-L, which is the metric contradicting itself.
64. DeepResearch Bench's E. Cit. counts supported statement-URL pairs with no upper bound, and Gemini-2.5-Pro Deep Research's 111.21 against Claude-3.5-Sonnet's 9.78 is largely a report-length difference, so optimizing E. Cit. means writing longer, not writing better.
65. DeepResearch Bench's C. Acc. is per-task precision that assigns 0 to any task producing no citable statements, which means a cautious short answer scores worse than a wrong one, and the two FACT metrics therefore pull in opposite directions by construction.
66. RACE cannot be interpreted as an absolute score at all, since it is a ratio against a Gemini-2.5-Pro reference report and 50 is parity, so a headline like "we scored 46" is meaningless without naming the reference and the judge, and the judge changed on 11 May 2026.
67. LitLLMs' citation coverage counts outputs whose citation count exactly equals the ground truth's, which is a formatting-compliance metric and not a correctness metric; GPT-4's 98.52% comes with the shortest outputs at 125.10 average words.
68. The whole reference-recall family, ours included, is undercut by 2605.29234's finding that only 51.4% of human citations clear a moderate relevance bar, so any single-number recall claim against a survey's own bibliography should be stated as coverage of a known-imperfect target, not as accuracy.
