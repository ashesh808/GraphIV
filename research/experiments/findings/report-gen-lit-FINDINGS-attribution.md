# How grounding, attribution and faithfulness are actually measured

Seven papers, all read from local HTML.
Every one had local full text, so nothing was skipped.
Baseline being compared against: GraphIV `03-01-attribution` 0.714 Gemma and 0.744 Qwen over 818 cited sentences, `03-02-checker-validity` 0.153 and 0.198 approval on broken citations.

---

## 1. ALCE, 2305.14627

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit for recall | a statement, defined as one sentence by sentence-boundary segmentation | Sec 2 |
| unit for precision | one citation | Sec 3.3 |
| judge | TRUE, a T5-11B model fine-tuned on a mixture of NLI datasets, run as a binary entailment function | Sec 3.2, 3.3 |
| premise | the concatenation of all passages the statement cites, each a 100-word chunk | Sec 2, 3.3 |
| citation recall | 1 for statement s_i iff it has at least one citation and phi(concat(C_i), s_i) = 1, averaged over statements | Sec 3.3 |
| citation precision | citation c is irrelevant iff phi(c, s_i) = 0 AND phi(concat(C_i minus c), s_i) = 1; c scores 1 iff s_i has recall 1 and c is not irrelevant | Sec 3.3 |
| corpus | Wikipedia 2018-12-20 for ASQA and QAMPARI, Sphere (filtered Common Crawl) for ELI5, 1,000 dev examples per dataset | Sec 2 |

1. ALCE caps citations at three per statement, so the metric never sees a densely cited sentence (Sec 2, footnote 4).
2. Precision is conditioned on recall, so a statement that fails recall contributes zero precision for all of its citations (Sec 3.3).

### Reported numbers

| system | protocol | cit. recall | cit. precision | section |
| --- | --- | --- | --- | --- |
| ChatGPT Vanilla, 5 passages, ASQA | text written by ChatGPT, judged by TRUE T5-11B, Wikipedia 100-word passages | 73.6 | 72.5 | Table 4 |
| ChatGPT Vanilla + Rerank, ASQA | same, best of 4 samples chosen by the metric itself | 84.8 | 81.6 | Table 4 |
| GPT-4 Vanilla, 5 passages, ASQA | text by GPT-4, same judge and corpus | 68.5 | 75.6 | Table 4 |
| GPT-4 Vanilla, 20 passages, ASQA | same | 73.0 | 76.5 | Table 4 |
| LLaMA-2-Chat-70B, 5 passages, ASQA | same | 62.9 | 61.3 | Table 4 |
| Vicuna-13B, 3 passages, ASQA | same | 51.1 | 50.1 | Table 4 |
| LLaMA-13B, 3 passages, ASQA | same | 10.6 | 15.4 | Table 4 |
| ChatGPT Vanilla, 5 passages, QAMPARI | text by ChatGPT, judged by TRUE, Wikipedia | 20.5 | 20.9 | Table 5 |
| ChatGPT Vanilla, 5 passages, ELI5 | text by ChatGPT, judged by TRUE, Sphere corpus | 51.1 | 50.0 | Table 6 |
| GPT-4 Vanilla, 5 passages, ELI5 | same judge and corpus | 44.0 | 50.1 | Table 6 |
| LLaMA-13B, 3 passages, ELI5 | same judge and corpus | 3.1 | 5.3 | Table 6 |

3. Human validation on ASQA gives human recall 74.7 and precision 76.6 against ALCE 75.3 and 74.4 for ChatGPT Vanilla, and on ELI5 50.8 and 52.4 against 52.8 and 50.4 (Sec 6, Tables 8 and 9).
4. Agreement between the human labels and the automatic metric is Cohen kappa 0.698 for citation recall and 0.525 for citation precision (Sec 6).
5. Treating the human annotations as the reference set, the automatic metric reaches 85.1% accuracy on recall and 77.6% on precision (Sec 6, App G.5).
6. On detecting insufficient citations it has recall 82.3 and precision 84.2, and on detecting irrelevant citations recall 75.6 and precision 66.1 (App G.5).

### Negative control

7. ALCE runs a gameability control, not a broken-citation control, and it is the only one of the four 2023 papers here that runs any adversarial arm at all (App D, Table 11).
8. Returning the top-1 retrieved passage verbatim and citing itself scores citation recall 99.4 and precision 99.4 while MAUVE fluency collapses to 20.8, and returning the first two sentences of that passage scores 98.7 and 98.7 with exact-match recall falling to 18.9 (Table 11).
9. That control shows the citation metric alone is trivially saturable by copying, which is why ALCE insists on reporting fluency and correctness beside it, but it never shows that the judge can reject a wrong citation.

### Stated limitations

10. "Our citation quality evaluation is limited by the accuracy of the NLI model; for citation precision, the NLI model cannot detect the case of 'partially support' and thus leads to a lower citation precision score than the human evaluation" (Limitations).
11. The metric cannot distinguish a citation that partially supports a statement from one that does not support it at all, and App E works the case through explicitly.
12. The metric cannot distinguish a well-sourced answer from a copied one, which is precisely what the App D control demonstrates.

---

## 2. FActScore, 2305.14251

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit | an atomic fact, "a short sentence conveying one piece of information" | Sec 3.1 |
| judge, reference version | human annotators from Upwork at 15 to 25 USD per hour, 4 USD per generation | Sec 3.3 |
| judge, estimator version | Inst-LLAMA 7B or ChatGPT prompted zero-shot with retrieved passages, prediction from the relative probability of True and False | Sec 4.1 |
| formula | f(y) = mean over atomic facts of the indicator that the fact is supported by knowledge source C, expectation taken only over non-abstaining responses | Sec 3.1 |
| corpus | English Wikipedia, retrieved with GTR | Sec 3.3, 4.1 |
| data | 183 people entities sampled from Wikidata, prompt "Tell me a bio of <entity>" | Sec 3.3 |

13. The three stated assumptions are that support is undebatable, that every atomic fact has equal weight, and that the knowledge source does not conflict with itself (Sec 3.1).
14. The atomic fact exists because a sentence is the wrong unit: "even a single sentence is a mix of supported and unsupported facts, e.g., in 40% of the cases with ChatGPT" (Sec 3.1).
15. FActScore rejects a partial-support label on the grounds that its "definition may be subjective and can lead to low agreement" (Sec 3.1).

### Reported numbers

| system | protocol | FActScore | section |
| --- | --- | --- | --- |
| InstructGPT | text by InstructGPT, judged by humans, Wikipedia | 42.5 | Table 1 |
| ChatGPT | text by ChatGPT, judged by humans, Wikipedia | 58.3 | Table 1 |
| PerplexityAI | text by PerplexityAI (with search), judged by humans, Wikipedia | 71.5 | Table 1 |

16. Label composition is 42.3 / 43.2 / 14.0 supported, not-supported, irrelevant for InstructGPT, 50.0 / 27.5 / 8.3 for ChatGPT, and 64.9 / 11.1 / 14.8 for PerplexityAI, with abstention 0.5 / 14.2 / 9.3 (Table 1).
17. Facts per response are 26.3, 34.7 and 40.8, over 6.2, 7.9 and 9.8 sentences, so the atomic-fact unit is roughly four times finer than the sentence (Table 1).
18. Human agreement on a 10% double-annotated slice is 96%, 90% and 88% for the three systems (Sec 3.3).

| estimator | error rate vs InstGPT / ChatGPT / PPLAI | ranking preserved | section |
| --- | --- | --- | --- |
| Inst-LLAMA No-context | 7.1 / 7.8 / 34.7 | no | Table 3 |
| Inst-LLAMA Retrieve to LM | 14.1 / 17.1 / 0.1 | no | Table 3 |
| Inst-LLAMA Retrieve to LM + NP | 1.4 / 0.4 / 9.9 | yes | Table 3 |
| ChatGPT No-context | 39.6 / 31.7 / 3.3 | no | Table 3 |
| ChatGPT Retrieve to LM | 5.1 / 6.8 / 0.8 | yes | Table 3 |
| ChatGPT Retrieve to LM + NP | 5.2 / 4.7 / 8.7 | yes | Table 3 |

19. The two best estimators correlate at Pearson r 0.99 across 13 subject models (Sec 4.3.2).
20. A proof of concept on 10 NLP-paper summary prompts scored against the ACL Anthology gives human 66.20 against model 73.61, error rate 7.41 (App B.5).

### Negative control

21. FActScore runs trivial-baseline controls and reports them in the main results table, which is the strongest control among the six pre-2026 papers here (Table 3, Table 9).
22. Always-Supported has error rate 57.5 / 41.7 / 28.5, Always-Not-supported 42.5 / 58.3 / 71.5, and Always-Random 7.5 / 8.3 / 21.5, and none of the three preserves the ranking between the three subject models (Table 3).
23. On the per-decision metric, Always-Not-supported reaches F1-micro 71.4 on InstructGPT, beating every retrieval-free estimator and beaten only by Retrieve-to-LM + NP at 83.2, so a degenerate always-reject judge nearly matches a real one at that class balance (Table 9, App B.2).
24. Always-Supported scores F1-micro 0.0 by construction, since F1-micro is computed on the not-supported class (App B.2).

### Stated limitations

25. "FActScore does not consider factual recall: the coverage of information in a generation", and it does not penalize frequent abstention or a low fact count (Limitations).
26. It "is not applicable when the facts are more nuanced, open-ended, and debatable" or where the knowledge source conflicts with itself (Limitations).
27. The estimator "is not perfect in individual judgments, and the best variant depends on the degree of how close a generation is to human-written text and its linguistic complexity" (Limitations).
28. Error rate and F1-micro rank estimators differently, and an estimator with better per-decision F1 can have a worse aggregate error rate if it is biased in one direction (App B.2, Figure 4).

---

## 3. Evaluating Verifiability in Generative Search Engines, 2304.09848

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit for recall | a verification-worthy statement, in practice a sentence | Sec 2.3, Limitations |
| unit for precision | one citation | Sec 2.4 |
| judge | human annotators, 34 of them, applying the AIS framework of Rashkin et al. | Sec 2.3, 3.3 |
| support test | a statement is fully supported iff a generic hearer would affirm "According to cited webpages C_i, s_i" in the context of the query and response | Sec 2.3 |
| citation recall | proportion of verification-worthy statements fully supported by their associated citations | Sec 2.3 |
| citation precision | (T_fs + T_ps) / N, where T_ps counts a partially supporting citation only when the union of citations fully supports the statement and no single citation does so alone | Sec 2.4 |
| corpus | the live web, whatever each commercial engine retrieved | Sec 3.1 |

29. Annotators first strip statements that are not verification-worthy, and the paper's position is that every statement about the external world is verification-worthy, so the filter removes almost nothing beyond self-reference and questions to the user (Sec 2.3).
30. This is the only paper here whose precision definition credits partial support, and it does so only under a union condition (Sec 2.4).

### Reported numbers

| system | protocol | recall | precision | section |
| --- | --- | --- | --- | --- |
| all four averaged | commercial engines, human judges, 1,450 queries each | 51.5 | 74.5 | Sec 4.2 |
| perplexity.ai | same | 68.7 | 72.7 | Sec 4.2 |
| NeevaAI | same | 67.6 | 72.0 | Sec 4.2 |
| Bing Chat | same | 58.7 | 89.5 | Sec 4.2 |
| YouChat | same | 11.1 | 63.6 | Sec 4.2 |

31. The query mix is 150 each from AllSouls, davinci-debate, ELI5 KILT, ELI5 Live and WikiHowKeywords plus 100 from each of seven NaturalQuestions subdistributions, 1,450 per system (Sec 3.2).
32. Inter-annotator agreement over 250 triple-annotated query-response pairs is above 82.0% pairwise with 91.0 F1 (Sec 3.3).
33. Recall on open-ended AllSouls essay questions falls to 44.3 and precision to 67.8, so the number moves with how extractive the question is (Sec 4.2).
34. Citation precision is inversely correlated with perceived utility, and Bing Chat's high precision comes with the lowest utility (Sec 4.3).

### Negative control

35. No negative control of any kind is reported.
36. There is no broken-citation arm, no trivial baseline, and no measurement of whether an annotator would reject a citation swapped for a wrong one.

### Stated limitations

37. "Verifiability is not factuality", and the metric never arbitrates whether a statement is true (Limitations).
38. "Sentences often have multiple claims. However, there is currently no clear linguistic definition on what constitutes a claim. As a result, we use sentences for simplicity and reproducibility" (Limitations).
39. The metric cannot distinguish a supported statement from a copied one: statements that are fully or partially supported have BLEU 31.3 and BERTScore 73.2 against the annotator-extracted evidence, and similarity correlates with citation precision at r 0.80, so "improved precision may largely be a byproduct of their increased tendency to copy or paraphrase" (Sec 4.4, Table 2).

---

## 4. Attributed Question Answering, 2212.08037

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit | one (question, short answer string, single passage) triple | Sec 3.1, 3.2 |
| judge, reference version | 5 trained human raters, majority vote, AIS guidelines | Sec 3.2, 5.2 |
| judge, automatic version | AutoAIS, a T5 11B checkpoint fine-tuned on MNLI, SNLI, FEVER, PAWS, SciTail and VitaminC, scored by force-decoding the positive label and thresholding at 0.5 | Sec 5.2 |
| support test | both "is all the information interpretable" and "is all the information fully supported by the source document" must be yes | Sec 3.2 |
| aggregate | proportion of test questions where the rater majority calls the output attributable | Sec 3.2 |
| corpus | a fixed attribution corpus, 1,000 randomly chosen NaturalQuestions questions | Sec 5.1, 5.2 |

40. The unit is a short answer string plus exactly one cited passage, not a sentence inside a long report, so nothing in this paper measures a multi-sentence document.

### Reported numbers

| system | protocol | EM | AutoAIS | human AIS | section |
| --- | --- | --- | --- | --- | --- |
| Retrieve-then-read | best RTR system, 5 human raters, 1,000 NQ questions | 41.1 | 66.3 | 65.5 +/- 1.5 | Table 1 |
| RTR + AutoAIS reranking | AutoAIS used as a system component, so not reported as a metric | 53.3 | not reported | 71.4 +/- 1.4 | Table 1 |
| Post-hoc retrieval | same protocol | 49.5 | 53.9 | 55.6 +/- 1.5 | Table 1 |
| Post-hoc + AutoAIS reranking | same | 49.5 | not reported | 59.0 +/- 1.5 | Table 1 |
| Low resource | same | 39.5 | 41.9 | 48.6 +/- 1.6 | Table 1 |
| LLM-as-retriever | same | 50.1 | 41.5 | 46.0 +/- 1.6 | Table 1 |

41. System-level Pearson correlation between human AIS and AutoAIS is 0.96, against 0.45 between human AIS and exact match (Sec 5.5).
42. Instance-level correlation is "much lower and more variable", and the paper recommends "care should be taken against reading individual AutoAIS scores too closely" (Sec 5.5).

### Negative control

43. No negative control is reported.
44. The paper does apply a leakage guard rather than a control: AutoAIS is not reported for the reranked systems because it was used to select their passages (Table 1 caption).
45. The reranked systems are the outliers to the 0.96 correlation, scoring lower on human AIS than the fit predicts, which is evidence that optimizing against the automatic judge degrades it (Sec 5.5).

### Stated limitations

46. AutoAIS "is fit-for-purpose as a development metric at the aggregate level (provided it is not used as a system component)", which is an explicit statement that it cannot distinguish per-instance attribution (Sec 5.5).
47. Exact match correlates poorly with attribution, and the paper concludes that its results "point to the limitation of reference answer corpora and string matching evaluation" (Sec 5.5).

---

## 5. Shallow Synthesis of Knowledge in GPT-Generated Texts, 2402.12255

### Metric definition

48. This paper measures no support relation at all, so it is not an attribution metric and should not be counted as one.

| item | value | section |
| --- | --- | --- |
| unit | an edge, defined as two citations co-occurring in the same sentence | Sec 3.5 |
| judge | deterministic graph statistics, no model and no human in the loop | Sec 3.5 |
| metrics | number of edges, average node degree, density, clustering coefficient | Table 1 |
| significance test | Mann-Whitney U with Holm-Bonferroni correction, n = 10 per condition | Sec 3.5 |
| corpus | 10 award-winning ACL 2023 papers, related work sections, cited works represented by title and abstract only from the Semantic Scholar API | Sec 3.3, 3.3.1 |

49. The generator only ever sees the title and abstract of each cited paper, never its body, so any measured shallowness confounds the model with the input it was given (Sec 3.3.1).

### Reported numbers

| statistic | human | GPT-assisted | GPT-4 alone | p, human vs GPT-4 | section |
| --- | --- | --- | --- | --- | --- |
| number of edges | 48.30 | 38.50 | 12.30 | 0.0202 | Table 2 |
| average node degree | 3.23 | 2.69 | 0.70 | 0.0020 | Table 2 |
| density | 0.14 | 0.13 | 0.02 | 0.0002 | Table 2 |
| clustering coefficient | 0.66 | 0.63 | 0.15 | 0.0034 | Table 2 |

50. Human versus GPT-assisted is not significant on any of the four statistics, with p from 0.9203 to 1.0000 (Table 2).
51. The related work sections carry between 8 and 52 citations each (Sec 3.3).

### Negative control

52. No negative control is reported.
53. There is no arm testing whether the graph statistics separate a genuinely synthesized text from one that merely packs citations into long sentences.

### Stated limitations

54. "Our evaluation based on citation graph analysis, while allowing scalable automated analysis, does not measure all facets that constitute quality, but rather should be seen as a proxy measure for cited work synthesis" (Sec 7).
55. "Even highly interconnected citation graphs may lack deeper integration of concepts", which is the paper stating that its metric cannot distinguish real synthesis from co-mention (Sec 7).
56. The sample is 10 papers, all best papers at one venue in one field, at one set of hyperparameters (Sec 7).

---

## 6. Self-RAG, 2310.11511

### Metric definition

57. Self-RAG defines no new attribution metric and reuses ALCE for citations and FActScore for biographies, so its unit and judge are inherited (Sec 4.1).

| item | value | section |
| --- | --- | --- |
| unit, ASQA | ALCE's statement for recall and citation for precision | Sec 4.1 |
| unit, Bio | FActScore's atomic fact | Sec 4.1 |
| judge, ASQA | ALCE's TRUE NLI model over the author-provided top-5 GTR-XXL passages | Sec 4.1, 4.3 |
| judge, Bio | the FActScore estimator | Sec 4.1 |
| judge, human arm | human annotators scoring S and P (plausible and supported) on 50 samples each from PopQA and Bio | Sec 5.3 |
| corpus | Contriever-MS MARCO top-5 plus web search for Bio and QA, author-provided GTR-XXL top-5 for ASQA | Sec 4.3 |

### Reported numbers

| system | protocol | ASQA cit. prec | ASQA cit. rec | Bio FActScore | section |
| --- | --- | --- | --- | --- | --- |
| Self-RAG 7B | Llama2-7B generator, ALCE TRUE judge, fixed GTR-XXL top-5 | 66.9 | 67.8 | 81.2 | Table 2 |
| Self-RAG 13B | Llama2-13B generator, same judge and passages | 70.3 | 71.3 | 80.2 | Table 2 |
| Retrieval-augmented ChatGPT | ChatGPT generator, same judge and passages | 65.1 | 76.6 | not reported | Table 2 |
| Retrieval-augmented Llama2-chat 13B | same judge and passages | 19.8 | 36.1 | 79.9 | Table 2 |
| Llama2 7B with retrieval | same judge and passages | 2.9 | 4.0 | 78.0 | Table 2 |
| Alpaca 13B with retrieval | same judge and passages | 2.0 | 3.8 | 77.7 | Table 2 |

58. Human evaluation on 50 samples gives S and P 92.5 on PopQA and 70.0 on Bio, with the model's own IsSup reflection token matching the annotator 90.0% and 85.0% of the time (Figure 3h).
59. The S and P arm excludes every instance where the model itself predicted irrelevant or no support, which biases that number upward and the paper states the exclusion plainly (Sec 5.3).
60. The critic's training labels came from GPT-4, whose reflection tokens agreed with the authors' own inspection at 95% for relevance, 95% for retrieval necessity, 90% for degree of support and 80% for usefulness (App A.1).
61. Raising the IsSup weight at inference raises ASQA citation precision and lowers MAUVE fluency, so the metric trades directly against fluency (Sec 5.3, Figure 3d).

### Negative control

62. No negative control is reported for the citation metric.
63. The closest thing is the low baselines at 2.0 to 2.9 citation precision for untuned Llama2 and Alpaca, which shows the metric has range but not that the judge can reject a wrong citation attached to a fluent sentence.

### Stated limitations

64. The paper does not state a limitation of the citation metric itself, since it treats ALCE as given.

---

## 7. Citation Grounding against a legal citation graph, 2606.00898

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit | one extracted statute citation string | Sec 4.1 |
| judge | an exact set-membership test against the node set of a citation graph, no model and no human | Sec 4.1 |
| formula | CG(r, G) = fraction of extracted citations that exist as nodes in G, defined as 1 when the response cites nothing | Sec 4.1 |
| decomposition | CP existence in the graph, CR co-citation with a semantically similar decision, CT in force at the relevant date, combined as CQ = mean over citations of CP times half of (CR + CT) | Sec 4.2 |
| graph | 100,753,415 decision nodes, 21,736 statute nodes, 502,231,421 edges, regex extraction at precision 1.00 on a 200-decision sample | Sec 3 |

65. This is the mechanical family our own no-hallucination guard belongs to, and it judges existence, never support.
66. CT as implemented checks existence in the graph rather than whether a specific version was in force, so the temporal component is not actually temporal yet (Limitations).

### Reported numbers

| system | protocol | mean CG | citations | flagged | density | section |
| --- | --- | --- | --- | --- | --- | --- |
| LEX Chat, Claude Sonnet 4 with RAG | 100 Ukrainian legal queries, regex extraction, membership test against 467,000 citation records | 0.873 | 290 | 57 | 2.9 | Table 1 |
| Claude Haiku 4.5 via Bedrock | same, temperature 0.3, no retrieval | 0.855 | 483 | 129 | 4.8 | Table 1 |
| Mistral Pixtral Large | same | 0.823 | 424 | 90 | 4.2 | Table 1 |
| Amazon Nova Pro | same | 0.822 | 386 | 87 | 3.9 | Table 1 |
| Amazon Nova Lite | same | 0.791 | 362 | 81 | 3.6 | Table 1 |

67. Citation density and grounding accuracy correlate at only rho -0.12 across the five systems, contradicting the assumed density-accuracy tradeoff (Sec 5.2).
68. By domain, constitutional law scores CG 1.00 for all five systems while family law ranges 0.46 to 0.78 and labor law 0.49 to 0.90 (Table 2).

### The finding that matters most for us

69. All 54 unique citations the metric flagged as hallucinations for the RAG production system were cross-referenced against a 25,136-article legislation database, and every one of them refers to a real, existing statute article (Sec 7.1).
70. 32 of the 54, or 59%, exist in the legislation database but are absent from the citation graph because courts rarely cite them, and the remaining 22 were confirmed real once the missing Family Code and Labor Code were imported (Sec 7.1).
71. The paper's own conclusion is that "CG thus provides a lower bound on citation accuracy, with the bound tightening as G grows", and that "it measures not only model accuracy but also the coverage of the ground-truth graph" (Sec 5.3).
72. For the one system whose flags were audited, the reported 12.7% hallucination rate was entirely a coverage artifact, and the metric's true reading is a graph-coverage measurement wearing a hallucination label.
72a. The other four systems' flags were never validated this way, so their 14.5% to 20.9% rates are unverified in the same direction.

### Negative control

73. A negative control exists, but on the training half rather than the measurement half (Sec 6.2, 6.5).
74. Four corruption strategies build rejected responses from real ones: article_swap replaces the article number within the same codex, law_swap keeps the number and changes the codex, hallucination substitutes a non-existent article, and anachronism substitutes a statute enacted after the decision date (Sec 6.2).
75. 2,244 decisions yield one corrupted pair each, split 1,795 / 224 / 225, and a DPO-trained model separates preferred from rejected at 98.5% held-out accuracy over three seeds with a rewards margin of 14.9 (Sec 6.3, 6.5, Table 3).
76. That 98.5% is a trained classifier's discrimination, not the CG metric's own ability to reject, and the paper says so: "the 98.5% accuracy measures discrimination between correct and corrupted citations on held-out data" (Limitations).

### Stated limitations

77. "G is built exclusively from court decisions and reflects only statutes that courts actually cite" (Limitations).
78. The metric produces false positives from coverage gaps but no false negatives, which the paper frames as a desirable asymmetry for legal use (Sec 7.1).
79. CG cannot distinguish a fabricated citation from a real one outside its graph, which is the same failure mode our own corpus-verification guard has for a real paper that is not on arXiv.

---

## 8. Verifier-dependent unsupported rates, 2607.20527

### Metric definition

| item | value | section |
| --- | --- | --- |
| unit | a claim-citation pair (c, p_i), where c is one generated sentence and p_i the passage it cites | Def 3.1 |
| judge | any of five verifiers, each validated against human labels before use | Sec 4.1, 5.1 |
| formula | unsupported-citation rate = fraction of claim-citation pairs with v(c, p_i) = 0 | Def 3.2 |
| premise protocol | the full cited passage tiled as 600-character windows at stride 300, supported if any window is attributable, claims capped at 600 characters | Sec 5.1 Verifiers |
| reference data | SciFact n = 208 for verifier validation plus a disjoint n = 802 split for prompt selection, QASA n = 1375 for calibration and re-attribution, PubMedQA n = 843 for a scope control | Sec 5.1 |
| generators audited | four open instruction-tuned models 27B to 35B from the Gemma-4 and Qwen3.6 families, run locally on one GPU, across OpenScholar, PaperQA2 and a bare no-retrieval floor, on ScholarQABench multi-paper tasks | Sec 5.1 |

80. Definition 3.2 states the rate "is meaningful only together with the verifier and protocol that produced it", which is the paper's whole thesis in one line.

### Reported numbers

| verifier | recall on supported | specificity | Cohen kappa | ROC-AUC | section |
| --- | --- | --- | --- | --- | --- |
| AttrScore-3B, adopted | 0.90 dev, 0.94 held-out | 0.54 dev, 0.48 held-out | 0.463 dev, 0.384 held-out | 0.88 [0.84, 0.93] | Table 2, S1, S2 |
| OpenScholar post-hoc | 0.50 | 0.92 | 0.339 | not reported | Table 2, S1 |
| GPT-4o | 0.46 | 0.92 | 0.305 | 0.87 [0.82, 0.92] | Table 2, S1 |
| RAGAS faithfulness | 0.30 | 0.96 | 0.195 | not reported | Table 2, S1 |
| DeBERTa-NLI | 0.25 | 0.97 | 0.164 | 0.90 [0.85, 0.94] | Table 2, S1 |

81. On identical agent outputs the measured unsupported rate runs from about 3% at the bare floor under the high-recall verifier to roughly 14 to 18% under the strict NLI judge, a threefold to sixfold swing driven by the instrument and not by the generator (Sec 5.3).
82. "Much of that climb is not extra unfaithfulness but extra false rejection: the strict verifiers have low recall on genuinely supported claims" at 0.25 against the human reference labels, "so their high rates partly count supported citations" (Sec 5.3).
83. On 300 deployment citations, three verifiers agree on what is supported at positive-specific agreement 0.90 to 0.96 but agree on what to flag at negative-specific agreement only 0.27 to 0.30, so 60 to 80% of the citations one verifier flags another calls supported (Sec 5.4, Table S3).
84. Cohen kappa between verifier pairs is 0.218 to 0.264 while observed agreement is 0.830 to 0.923 and Gwet AC1 is 0.784 to 0.914, which the paper attributes to the base-rate paradox and is why it reports class-specific agreement instead (Table S3, App S2).
85. The conformal flag rule hits its declared catch rate on held-out splits, with targets 0.90 / 0.94 / 0.98 achieved at 0.90 / 0.94 / 0.98 on QASA n = 1375 (Sec 5.5).
86. At a 90% guarantee the review budget is 2.5% of cited sentences for the bare model, 3.3% for OpenScholar and 6.1% for PaperQA2, pooled over the four open models (Sec 5.5, Table 3).
87. Re-attribution recall@1 on QASA is 0.76 for Gemma-4-26B self-attribution, 0.69 for BM25 on CPU, 0.58 for the verifier score and 0.51 for Qwen3.6-27B (Table 4).

### Negative control

88. This paper runs four distinct controls and is the only one of the seven whose controls test the measurement instrument rather than the generator.
89. Random re-attribution scores recall@1 0.03 against 0.51 to 0.76 for real rankers, establishing the floor (Table 4).
90. A scope control on PubMedQA gives kappa 0.02 over n = 843, which the paper calls "the intended result: the verifier checks whether a passage supports a claim, not whether a conclusion is correct" (Sec 5.8).
91. A lexical control shows an answer and a refuting passage share almost identical vocabulary on SciFact (Jaccard 0.064 against 0.055) while the verifier separates them (mean attributability 0.83 against 0.50), so a lexical ranker cannot judge support versus contradiction (Sec 5.6, App S4).
92. The calibration-negative-difficulty control is the sharpest: a threshold calibrated to catch 90% of easy in-paper distractors (verifier mean score 0.20) catches only 37% of harder human-labeled negatives (mean score 0.50), and 44% and 61% at the 94% and 98% targets (Sec 5.5, App S6).
93. Point 92 is the direct warning for any broken-citation control including our own: the difficulty of the constructed negative sets the apparent catch rate.

### Stated limitations

94. "The unsupported-citation rate is relative to a verifier's operating point, so our numbers and any others in this literature are interpretable only together with the verifier and protocol that produced them" (Sec 7).
95. "Truncating the passage to a fixed prefix, a tempting shortcut, inflates the apparent unsupported rate severalfold and must be avoided" (Sec 7).
96. "Two unsupported rates from different papers are not comparable unless they name the same verifier and protocol" (Sec 5.3).
97. The audit isolates the generation step with retrieval held fixed, so it does not capture errors a system's own retrieval would introduce (Sec 7).
98. The metric cannot distinguish an unsupported citation from one the verifier is simply too strict to accept, which is what the 3% to 18% spread demonstrates.

---

## 9. Cross-paper summary

| paper | metric | unit of judgement | judge | headline number | negative control |
| --- | --- | --- | --- | --- | --- |
| 2305.14627 | citation recall | statement, one sentence | TRUE T5-11B NLI | 73.6 ChatGPT ASQA | gameability only (copy shortcut scores 99.4) |
| 2305.14627 | citation precision | one citation | TRUE T5-11B NLI | 72.5 ChatGPT ASQA | same |
| 2305.14251 | FActScore | atomic fact | humans, then Inst-LLAMA 7B or ChatGPT with GTR retrieval | 42.5 / 58.3 / 71.5 human | yes, three trivial baselines in the main table |
| 2304.09848 | citation recall | verification-worthy statement, one sentence | 34 human annotators, AIS | 51.5 averaged over 4 engines | none |
| 2304.09848 | citation precision | one citation, partial credited | same | 74.5 averaged | none |
| 2212.08037 | human AIS | (question, short answer, one passage) | 5 human raters, majority vote | 65.5 best retrieve-then-read | none, only a leakage guard |
| 2212.08037 | AutoAIS | same triple | T5-11B NLI at threshold 0.5 | 66.3 | none |
| 2402.12255 | citation graph density, degree, clustering | an edge, two citations in one sentence | deterministic graph statistics | density 0.14 human against 0.02 GPT-4 | none |
| 2310.11511 | ALCE citation prec / rec | inherited from ALCE | inherited TRUE T5-11B | 70.3 / 71.3 Self-RAG 13B | none |
| 2310.11511 | S and P | one output, filtered | human, 50 samples | 92.5 PopQA, 70.0 Bio | none |
| 2606.00898 | citation grounding CG | one citation string | set membership in a citation graph | 0.791 to 0.873 | yes, but for a DPO classifier, not for CG itself |
| 2607.20527 | unsupported-citation rate | claim-citation pair, one sentence plus its passage | five verifiers spanning recall 0.25 to 0.90 | 3% to 18% on the same outputs | yes, four of them, all on the instrument |
| GraphIV 03-01 | cited-sentence support | one cited sentence, any-one-of pass | Gemma-4-26B and Qwen3.6-35B, yes/partial/no, only yes counts | 0.714 / 0.744 | yes, nearest-cited-paper swap, 0.153 / 0.198 |

99. Six of the twelve published metrics have no negative control at all, and two of the three that have one control something other than the metric they headline.
100. Only 2607.20527 and GraphIV 03-02 test whether the judge behind the headline number can return a negative on text that looks right.

---

## 10. What we can compute more cheaply or more reliably because we hold the cited paper's full text

101. ALCE citation recall and precision (2305.14627 Sec 3.3) need a passage index at evaluation time, and we can run the same TRUE-style entailment with the premise selected from the cited paper's own body, which removes the "supported but the passage was not in context" failure that ALCE's 100-word chunking creates.
102. 2607.20527's sliding-window protocol (Sec 5.1, Sec 7) tiles the cited passage at 600 characters and stride 300 and warns that a fixed prefix "inflates the apparent unsupported rate severalfold", and we are the only setup here that can tile the entire document for every citation offline, so we can measure the size of that inflation instead of assuming it.
103. FActScore's expensive step is GTR retrieval over Wikipedia for each atomic fact (2305.14251 Sec 4.1), and for a report where every atomic fact is attached to a named arXiv id the knowledge source collapses to one document we already hold, so atomic-fact precision costs a within-document search rather than a corpus retrieval.
104. 2305.14251 App B.5 already proves the domain transfer we would need, running FActScore over the ACL Anthology at error rate 7.41 on 10 NLP-paper prompts, so the atomic-fact unit is known to survive the move from biographies to papers.
105. 2606.00898's CG (Sec 4.1) is free for us and equals 1.000 by construction, and the interesting quantity is not CG but the fraction of a report's citations that fall outside arXiv, which their Sec 7.1 result says is exactly what a corpus-membership metric silently reports.
106. 2402.12255's four graph statistics (Table 1) are deterministic and free on our own reports, and because we hold 72.8M resolved edges we can compute the statistic they could not: whether two papers co-cited in one of our sentences actually cite each other or share a citation, which turns their proxy for synthesis into a checkable claim.
107. Point 106 has a known negative result waiting for it: `03-03-graph-digest` already found support falls from 0.754 to 0.707 when the adjacency digest is in the prompt, so higher co-citation density in our text is not evidence of better grounding and would need to be reported against support, not instead of it.
108. Nothing in 2304.09848 or 2212.08037 gets cheaper for us, since both are human-judged by design and their cost is annotator time, not retrieval.

---

## 11. Is any of them a fair comparison point for 0.714 and 0.744

109. None of the seven is a fair comparison point as a number, and the correct statement is that our number has no published peer at the moment.
110. 2305.14627 ALCE 73.6 is the nearest-looking number and the least fair, because the judge is a T5-11B NLI entailment model rather than an instruction-following LLM answering a three-way rubric, the premise is a 100-word Wikipedia chunk rather than the cited paper, the domain is ambiguous factoid QA rather than a scientific literature review, and ALCE requires the concatenation of a statement's citations to entail it while we pass a sentence when any one of its cited papers supports it.
111. The closeness of 73.6 to 0.714 is a coincidence of two unrelated measurements and must never be written as agreement.
112. 2310.11511 Self-RAG 66.9 and 70.3 inherit ALCE wholesale (Sec 4.1), so every objection in point 110 applies unchanged.
113. 2304.09848's 51.5 is unfair in the opposite direction: the judge is 34 trained humans applying AIS rather than a model, and a human-judged rate and a model-judged rate are different measurements of different things even when the unit matches.
114. 2212.08037's 65.5 is unfair on the unit: it judges a short answer string against exactly one passage, and our unit is a sentence in a multi-page report that may carry several citations.
115. 2305.14251's 42.5 to 71.5 is unfair on the unit in the sharpest way, because FActScore exists precisely to reject the sentence as a unit, reporting that a single sentence mixes supported and unsupported facts in 40% of ChatGPT cases (Sec 3.1), so a sentence-level rate and an atomic-fact rate are not on the same scale by construction.
116. 2402.12255 reports no support rate at all and is not a comparison point in any sense.
117. 2606.00898's 0.791 to 0.873 measures whether a citation identifier exists in a graph, which is our mechanical guard's metric and not our support metric, and comparing it to 0.714 would be comparing existence to support.
118. 2607.20527 is the closest by generator and by unit and is still not a fair comparison, but it is the one worth engaging with in detail.

### Why 2607.20527 is close and still not comparable

119. It is close because it audits Gemma-4 and Qwen3.6 models at 27B to 35B run locally on scientific synthesis tasks, which is our exact generator class and task class (Sec 5.1).
120. It is close because its unit, a claim-citation pair of one generated sentence and its cited passage, is the same object our checker scores (Def 3.1).
121. It is not comparable because it checks the claim against the passage the pipeline actually had in its context, while we check against passages retrieved from the cited paper's full text, which is a strictly harder and differently-shaped premise set.
122. It is not comparable because it scores every claim-citation pair separately while we score a sentence once and pass it when any one of its cited papers supports it, which inflates our rate relative to theirs whenever a sentence carries several citations.
123. It is not comparable because its adopted verifier sits at recall 0.94 and specificity 0.48 on held-out data (Table S2), a deliberately lenient operating point, while our headline counts only "yes" from a yes/partial/no rubric and discards partial.
124. Its own rule settles the question: "two unsupported rates from different papers are not comparable unless they name the same verifier and protocol" (Sec 5.3).
125. The one comparison that is legitimate is on the instrument rather than the output, because 03-02 gives our checker a supported-class approval of 0.714 Gemma and 0.744 Qwen and a rejection rate on constructed negatives of 0.847 and 0.802, which in their vocabulary reads as recall 0.71 to 0.74 at specificity 0.80 to 0.85.
126. Placed on their frontier in Table 2, that operating point sits between OpenScholar post-hoc (0.50 / 0.92) and AttrScore-3B (0.90 / 0.54) and is closer to balanced than any of their five verifiers, which is a real and defensible claim about our judge.
127. The caveat on point 126 is point 92: their calibration-negative experiment shows apparent catch rate is set by how hard the constructed negative is, so our 0.85 catch rate is only credible because 03-02 swaps in the nearest cited paper rather than a random one, a choice their result independently vindicates.
128. Our `03-04` failure to label uncited sentences (kappa 0.003) is not a novel failure and was predicted in 2305.14251 Sec 3.1, which rejected a partial-support label because its "definition may be subjective and can lead to low agreement" and answered it with the atomic fact, so the atomic fact is the known fix for the exact question that defeated us.
