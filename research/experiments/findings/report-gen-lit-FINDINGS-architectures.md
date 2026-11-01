# Report generation architectures, ten systems

Every claim below names the arxiv id and the section it was read from.
Where a paper does not report a number, this file says so instead of estimating.
SciSage (2506.12689) has a broken ar5iv conversion, so it was read from the local PDF; section numbers are the PDF's own.

## Scope: not all ten do the same job

| id | system | output | input pool | who chooses the references |
| --- | --- | --- | --- | --- |
| 2406.10252 | AutoSurvey | 8k to 64k token survey | 530k arXiv CS papers | the system retrieves |
| 2503.04629 | SurveyForge | ~64k token survey | 600k papers plus 20k survey outlines | the system retrieves |
| 2502.14776 | SurveyX | survey, length not stated | 2.63M arXiv plus a Scholar crawler | the system retrieves |
| 2504.08762 | InteractiveSurvey | survey, length not stated | arXiv API, avg 45.2 refs per topic | the system retrieves, the user edits |
| 2506.12689 | SciSage | survey, max 6 sections | arXiv, PubMed, Google Scholar APIs | the system retrieves |
| 2402.14207 | STORM | Wikipedia-style article | open web via You.com | the system retrieves |
| 2504.05732 | LLMxMapReduce-V2 | survey, 7k to 47k tokens | 23 to 280 full papers, given | given by the benchmark |
| 2403.02574 | ChatCite | one related-work section | 63.59 refs avg, given | given by the dataset |
| 2411.14199 | OpenScholar | one long-form answer, ~2x a human answer | peS2o, 45M papers, 234M passages | the system retrieves |
| 2408.07884 | Instruct LLMs | survey | 80 to 100 refs, given, titles only | given by NLPCC 2024 |

1. Only 2504.05732, 2403.02574 and 2408.07884 are given their reference list, so their numbers are not comparable to systems that must retrieve (2504.05732 sec 4.2, 2403.02574 sec 5.1, 2408.07884 sec 3.1).
2. 2411.14199 produces a single long answer, not a sectioned survey, so its per-query cost is not a survey cost (2411.14199 sec 5.2).

---

## 1. AutoSurvey (2406.10252)

### Pipeline

| step | what happens | context per call |
| --- | --- | --- |
| retrieve | 1,200 papers by topic embedding | n/a |
| outline | abstracts split into 30,000-token chunks, one outline per chunk, then one merge call | 30k tokens of abstracts |
| section outline | per section, expand into subsections with descriptions | overall outline plus a paper list |
| draft | per subsection, in parallel | overall outline, 60 papers at 1,500 tokens each, subsection name, description |
| citation reflection | per subsection | the same 60 papers plus the drafted subsection |
| coherency refinement | per subsection | previous subsection, following subsection, the subsection |
| select | N=2 whole surveys generated, the better one kept | whole documents |

1. The outline is fixed at 8 sections and is produced by chunk-and-merge over abstracts only, never full text (2406.10252 sec 4.1 Setup).
2. Subsections are drafted fully in parallel and never see each other during drafting (2406.10252 Algorithm 1, line 8).
3. Coherency refinement is the only place a subsection sees a neighbor, and it sees exactly one on each side (2406.10252 Appendix F, COHERENCY_REFINEMENT_PROMPT).
4. The revision loop has no trigger and no stopping condition, it runs once over every subsection unconditionally (2406.10252 sec 2, Integration and Refinement).
5. Citations are written as paper titles inside brackets, then each generated title is embedded and snapped to the nearest real title in the database (2406.10252 Appendix B).
6. The reference list is therefore assembled after generation from a nearest-neighbor match, not from ids the writer was handed (2406.10252 Appendix B).

### Model calls and cost

1. A 32k-token survey costs 3,009.7K input tokens and 112.9K output tokens (2406.10252 Appendix D, Table 7).
2. That is $0.89 on Claude-3-Haiku, $11.72 on Gemini-1.5-Pro and $33.48 on GPT-4 (2406.10252 Appendix D, Table 7).
3. Speed at 64k tokens is 73.59 surveys per hour, against 12.56 for naive RAG and 0.07 for humans (2406.10252 sec 4.3, Table 2).
4. The introduction separately claims $1.2 and 3 minutes per survey, which does not reconcile with 73.59 per hour (2406.10252 sec 1).
5. The number of LLM calls per report is not reported.
6. The drafting model is Claude-3-Haiku with a 200k context, and evaluation uses GPT-4, Claude-3-Haiku and Gemini-1.5-Pro (2406.10252 sec 4.1).

### Because they have no citation graph and no full text

1. The chunk-and-merge outline exists only because 1,200 abstracts do not fit a context window, a graph would let them pick 100 structurally important papers instead (2406.10252 sec 2.1).
2. Title-embedding snapping exists only because the model is not handed stable paper ids it can cite (2406.10252 Appendix B).
3. Papers are truncated to the first 1,500 tokens because full text is not indexed, which throws away results and comparisons (2406.10252 sec 4.1).

### What would degrade on a 26B model

1. Their own ablation says the pipeline is model-robust: Claude-3-Haiku scores 4.58 average against GPT-4 at 4.70 and human at 4.70 (2406.10252 sec 4.3, Table 4).
2. Citation recall is actually highest on the small model, 82.45 for Claude-3-Haiku against 80.25 for GPT-4 (2406.10252 sec 4.3, Table 4).
3. The fragile step is COHERENCY_REFINEMENT_PROMPT, which orders the model in all caps not to touch bracketed citations while rewriting the prose around them (2406.10252 Appendix F).

---

## 2. SurveyForge (2503.04629)

### Pipeline

1. Two databases are kept, 600k research papers and 20k human survey outlines, both encoded with gte-large-en-v1.5 (2503.04629 Appendix A.1).
2. The first-level outline is generated from papers retrieved for the topic plus outlines retrieved for the topic, so structure is copied from real surveys (2503.04629 sec 3.1).
3. Each first-level heading carries a semantic query, and each second-level heading carries a sub-query, both generated with the heading (2503.04629 sec 3.1).
4. The papers retrieved while writing a section are stored as memory M_i, and reused to decompose that section's query at writing time (2503.04629 sec 3.2.1, Algorithm 1).
5. The temporal-aware reranking engine buckets retrieved papers into two-year groups and keeps the most-cited within each bucket, proportional to bucket size (2503.04629 sec 3.2.1, eq 3).
6. Sections are written fully in parallel, then one refinement pass runs over the concatenation to remove cross-section redundancy (2503.04629 sec 3.2.2).
7. There is no critique loop and no trigger, refinement is a single unconditional pass (2503.04629 sec 3.2.2).
8. Retrieval budgets copy AutoSurvey exactly: 1,500 candidates for the outline and 60 papers per chapter (2503.04629 sec 4.1).

### Model calls and cost

1. A ~64k-token survey takes 2.37M input tokens and 0.13M output tokens (2503.04629 Appendix A.6).
2. That is $0.43 on GPT-4o-mini and about 10 minutes end to end, subject to API rate limits (2503.04629 Appendix A.6).
3. DeepSeek-v3 costs $0.37 per survey and beats both closed models on every metric they report (2503.04629 Appendix A.5, Table 7).
4. The number of LLM calls per report is not reported.

### The numbers that matter to us

1. Input coverage, meaning the overlap between the retrieved pool and the human reference set, is 0.2231 for SurveyForge and 0.1153 for AutoSurvey (2503.04629 sec 4.2, Table 1).
2. Reference coverage, the overlap between what the survey actually cites and the human reference set, is 0.3960 against a human-written 0.6294 (2503.04629 sec 4.2, Table 1).
3. So the best retrieval-based system in this table finds under a quarter of the papers a human would have read.
4. Retrieving human outlines instead of random ones lifts outline quality from 81.78 to 86.67, and random outlines alone already lift it to 84.58 (2503.04629 sec 4.4).

### Because they have no citation graph and no full text

1. The citation counts used in the reranker come from paper metadata, not from a graph they own, so influence is a scalar and not a structure (2503.04629 sec 3.2.1).
2. Their own limitations section names the failure this causes: no comparative analysis of methodological evolution, defaulting to mechanical reference listing (2503.04629 Limitations).

### What would degrade on a 26B model

1. Nothing measured, and the open-model result points the other way, since DeepSeek-v3 scores 80.15 against GPT-4o-mini at 77.06 (2503.04629 Appendix A.5).

---

## 3. SurveyX (2502.14776)

### Pipeline

1. Reference recall runs a keyword expansion loop that stops at 1,000 documents (2502.14776 sec 3.1.1, Algorithm 1).
2. Each round searches, clusters the abstracts, names each cluster, and adds the one keyword farthest from the pool and closest to the topic (2502.14776 Algorithm 1).
3. Filtering is two-stage, embedding top-K first and then an LLM pass for fine-grained relevance (2502.14776 sec 3.1.1).
4. Every reference is compressed into an AttributeTree using one of four templates by paper type: method, benchmark, theory, survey (2502.14776 sec 3.1.2, Appendix B).
5. The primary outline comes from the LLM's internal knowledge alone, which they found sufficient at that level (2502.14776 sec 3.2.1).
6. Secondary outlines come from per-reference hints, then all secondary headings are stripped out, deduplicated as a flat list, and reattached (2502.14776 sec 3.2.1).
7. During writing, a subsection can see the other subsections' content, so drafting is not fully independent (2502.14776 sec 3.2.2).
8. Post-refinement uses each drafted paragraph as a retrieval query back into the attribute forest, then rewrites the paragraph to drop irrelevant citations and add relevant ones (2502.14776 sec 3.2.3).
9. Figures and tables are produced by filling script templates from attribute-tree fields, and figures are also lifted from reference PDFs by an MLLM (2502.14776 sec 3.2.3).

### Model calls and cost

1. No token counts, dollar cost, wall-clock time or LLM call count are reported anywhere in the paper.
2. The whole pipeline runs on GPT-4o with bge-base-en-v1.5 embeddings (2502.14776 sec 4.2).

### The ablation that matters most to us

| removed | citation F1 | content avg |
| --- | --- | --- |
| nothing | 81.52 | 4.590 |
| RAG-based rewriting | 55.16 | 4.55 |
| AttributeTree, replaced by full text | 58.23 | 4.32 |
| outline optimization | 80.92 | 4.32 |
| keyword expansion | 76.01 | 4.48 |

1. Handing the model raw full text instead of a structured attribute tree costs 23 points of citation F1, from 81.52 to 58.23 (2502.14776 sec 4.3, Table 2).
2. That is the single most important warning for us: full text is only an advantage after it has been distilled into typed fields.
3. Removing the post-hoc citation rewriting costs 26 points of citation F1, from 81.52 to 55.16, more than any other component (2502.14776 sec 4.3, Table 2).

### Because they have no citation graph and no full text

1. The keyword expansion loop is a substitute for graph traversal, it grows coverage by guessing vocabulary rather than by following edges (2502.14776 sec 3.1.1).
2. They run their own Google Scholar crawler because their offline arXiv dump has no way to reach beyond it (2502.14776 sec 3.1.1).

### What would degrade on a 26B model

1. Nothing measured, they never vary the model.

---

## 4. InteractiveSurvey (2504.08762)

### Pipeline

1. The topic is expanded by an LLM into a description, then into themes, entities and concepts, which are assembled into an arXiv API boolean query (2504.08762 sec 3.1).
2. If the hit count is under MIN_REF the constraints are relaxed and the search repeats, then results are truncated to MAX_REF (2504.08762 sec 3.1).
3. Every PDF is parsed to Markdown with MinerU, chunked at fixed length and embedded into a vector store (2504.08762 sec 3.2).
4. Categorization uses 10 HyDE pseudo-documents per user-chosen criterion, retrieves chunks per paper, and writes a per-paper description for that criterion (2504.08762 sec 3.3.1).
5. Those descriptions are agglomeratively clustered, and the cluster names become section titles, so the outline is a clustering result and not an LLM plan (2504.08762 sec 3.4).
6. The outline is produced as a fill-in-the-blanks template rather than free generation, which they say is what makes it work with weaker LLMs (2504.08762 sec 3.4).
7. Subsections are written in parallel within a section, then summarized, then merged into the section (2504.08762 Appendix A.2, Algorithm 2).
8. Abstract, introduction, future directions and conclusion are written last from the already-generated section content (2504.08762 sec 3.5).
9. There is no revision or critique loop at all, the human is the loop (2504.08762 sec 3.5).
10. Citations are attached after writing, per sentence, by cosine similarity against reference chunks with an adaptive threshold tau = max(tau_static, mu + k sigma) (2504.08762 Appendix C).

### Model calls and cost

1. One survey takes 2,077.8 seconds, about 35 minutes, on qwen2.5-72b-instruct with an RTX 3090 for parsing (2504.08762 sec 4.2).
2. Reference parsing and reference categorization dominate that time, not generation (2504.08762 sec 4.2).
3. The average topic has only 45.2 references (2504.08762 sec 4.2).
4. No token counts, dollar cost or LLM call count are reported.

### Because they have no citation graph and no full text

1. Most of the 35 minutes is spent downloading and OCR-parsing PDFs that we already hold parsed on disk (2504.08762 sec 4.2).
2. The 45.2-reference pool is a direct consequence of having to fetch and parse each paper, which caps breadth at two orders of magnitude below our corpus.

### What would degrade on a 26B model

1. They deliberately built the fill-in-the-blanks outline format because end-to-end outline generation fails on less powerful LLMs, and they say so (2504.08762 sec 3.4).
2. Their whole system runs on qwen2.5-72b, so a 26B is one step further down that same axis (2504.08762 sec 4.2).

---

## 5. SciSage (2506.12689)

### Pipeline

| agent | job |
| --- | --- |
| Interpreter | detect language, translate, infer intent, domain and topic, rewrite the query |
| Organizer | pick an outline template, ensemble outlines from several LLMs, emit per-section search queries |
| Collector | multi-source retrieve, rerank on recency, venue, author influence and citations |
| Composer | write each subsection from titles, abstracts and full texts, extract figures |
| Reflector | critique at outline, section and full-text level |
| Refiner | dedupe references, renumber citations, export LaTeX or Markdown |

1. The outline is an ensemble: Qwen3-14B, Qwen3-32B and Llama3-70B each generate one, then they are merged (2506.12689 Appendix C).
2. The outline is capped at 6 sections with a minimum depth of 2, and is refined for up to 2 reflection rounds (2506.12689 Appendix C).
3. Sections are written and reflected on one at a time, with up to 2 section-level reflection rounds each (2506.12689 Algorithm 1, lines 11 to 20).
4. Section reflection can trigger new retrieval by the Collector, so the loop is retrieval-augmented and not just rewriting (2506.12689 sec 3.3).
5. Full-text reflection runs a panel of LLM personas, journal editor, senior professor, peer reviewer, and takes a majority vote to mark sections for rework (2506.12689 sec 3.3).
6. Termination is by empty feedback or a max trial count, whichever comes first (2506.12689 Algorithm 1, line 9 and line 19).

### Model calls and cost

1. Every baseline and SciSage itself runs on Qwen3-32B, which is the closest published setup to our 26B target (2506.12689 sec 6.1).
2. No token counts, dollar cost, wall-clock time or LLM call count are reported.

### The number that matters most to us

| system | reference F1 vs human citations | TP out of 3,844 |
| --- | --- | --- |
| SciSage | 0.46 | 1,510 |
| AutoSurvey | 0.14 | 392 |
| OpenScholar with SciSage outlines | 0.061 | 156 |
| LLMxMapReduce-V2 | 0.017 | 130 |

1. SciSage recovers 1,510 of 3,844 human-cited references, against 392 for AutoSurvey, on the same benchmark and the same 32B model (2506.12689 sec 6.2.1, Table 4).
2. Disabling reflection costs 8 points of critical thinking, 69.70 to 77.93, and 10 points of document structure, 71.25 to 81.48 (2506.12689 sec 7.2, Table 6).
3. So on a 32B model, the reflection loop is worth a lot, which contradicts the OpenScholar 8B result below and suggests a size threshold somewhere between 8B and 32B.

### What their 32B model still fails at

1. Human evaluators found the output lacks depth, gets mathematical expression wrong, and complicates sentence structure, preferring the human survey in most pairs (2506.12689 sec 6.2.2).

---

## 6. STORM (2402.14207)

### Pipeline

1. Related topics are generated, their Wikipedia tables of contents are fetched, and from those N=5 writer perspectives are induced (2402.14207 sec 3.1).
2. A sixth basic-fact perspective is always added so the ordinary information is not missed (2402.14207 sec 3.1).
3. Each perspective runs an M=5 turn simulated conversation between a writer and a grounded expert, in parallel across perspectives (2402.14207 sec 3.2, sec 4.4).
4. Each question is decomposed into search queries, results are filtered by a rule-based trust filter, and the surviving sources are appended to the reference pool R (2402.14207 sec 3.2).
5. A draft outline is written from the topic alone, using only parametric knowledge, and is then refined against all six conversations (2402.14207 sec 3.3).
6. Sections are written in parallel, each retrieving from R by its own title plus all its subsection headings, using Sentence-BERT similarity (2402.14207 sec 3.4).
7. The only post pass is a deduplication call over the concatenated article, plus a lead-section summary (2402.14207 sec 3.4).
8. There is no critique loop and no revision trigger.

### Model calls and cost

1. gpt-3.5-turbo asks questions, gpt-3.5-turbo-instruct does the rest, gpt-4 does the outline and the final article (2402.14207 sec 4.4).
2. No token counts, dollar cost, wall-clock time or LLM call count are reported.
3. The full pipeline collects 99.83 unique references on average, against 54.36 without perspectives and 39.56 without conversation (2402.14207 sec 5.2, Table 5).

### What would degrade on a 26B model

1. They state outright that gpt-3.5 is not faithful to sources when generating text with citations, so they use gpt-4 for the final article (2402.14207 sec 4.4).
2. That is the sharpest published statement of the small-model citation failure, and it is exactly the risk for a 26B writer.

### The failure mode they name

1. Expert editors gave low verifiability scores not for hallucinated facts but for unverifiable connections drawn between two real retrieved facts, which they call red herring or overspeculation (2402.14207 sec 6).
2. Seven of ten editors said the output sounds emotional or unneutral, because tone transfers from the retrieved web sources (2402.14207 sec 6).
3. Both failures come from the sources being web pages, and neither would be diagnosed by a citation-existence check.

---

## 7. LLMxMapReduce-V2 (2504.05732)

### Pipeline

1. There is no retrieval, the full text of every reference is given, 23 to 280 papers and up to 4.66M tokens per topic (2504.05732 sec 4.2, Appendix B.2, Table 3).
2. References are clustered, one local skeleton is generated per cluster, and the locals are merged into skeleton S0 (2504.05732 sec 3.1).
3. Every skeleton node carries two fields, Digest Construction saying what to pull out of a paper, and Digest Analysis saying how to use it when writing (2504.05732 sec 3.1, Figure 2).
4. Each reference is compressed into a digest that the current skeleton dictates, and the same call also emits feedback on the skeleton (2504.05732 sec 3.1).
5. Skeleton edits are residuals, delta S, never a regenerated skeleton, so intermediate versions stay comparable (2504.05732 sec 3.2).
6. An LLM-as-judge scores each candidate skeleton out of ten and that score is used as an information entropy estimate (2504.05732 sec 3.2).
7. Feedback items are sampled with probability proportional to entropy and combined over 6 convolution layers with kernel width 3, result num 10, top-k 6 (2504.05732 sec 3.2.1, Appendix C.4).
8. Then 3 rounds of best-of-3 self-refinement pick the highest-entropy skeleton (2504.05732 sec 3.2.2, Appendix C.4).
9. Digests are regenerated against the final skeleton before writing, so every reference is digested at least twice (2504.05732 sec 3.3).
10. Leaf sections are written from the skeleton node plus the digests, non-leaf sections additionally receive their children's finished text, so writing is bottom-up and not flat (2504.05732 sec 3.3).
11. Their measured optima are 7 convolution layers, width 3, and 3 self-refinement steps, past which quality falls (2504.05732 sec 4.5).

### Model calls and cost

1. No token counts, dollar cost, wall-clock time or LLM call count are reported.
2. The call count is structurally large: at least 2 x |R| digest calls plus one entropy judge call per candidate skeleton across 6 layers at result num 10.
3. All baselines and the system run on Gemini-2.0-flash-thinking-exp-1219 (2504.05732 sec 4.2).

### Their reference metric is not a retrieval metric

1. Reference precision counts how many of the given input references got cited at least once, so 95.50 measures utilization, not correctness (2504.05732 Appendix D.1.4).
2. On a benchmark where references must be retrieved, this same system scores reference F1 0.017, the worst of four (2506.12689 sec 6.2.1, Table 4).

### What is worth stealing

1. The skeleton node carrying an explicit extraction instruction and an explicit analysis instruction is the cleanest published way to make per-paper extraction question-specific (2504.05732 sec 3.1).
2. Writing a parent section from its children's finished text is the only published fix for parents that repeat their children (2504.05732 sec 3.3).

---

## 8. ChatCite (2403.02574)

### Pipeline

1. Each paper, target and references alike, is reduced to answers to seven fixed guiding questions, which is the entire compression step (2403.02574 sec 3.1).
2. Generation is strictly sequential over references, one reference added per turn, never parallel (2403.02574 sec 3.2.3, Algorithm 1).
3. Each turn generates n_s continuations from each of n_c surviving drafts, so the search is a beam over draft states (2403.02574 sec 3.2.1).
4. An LLM evaluator votes n_v times on each candidate, and the top n_c by vote survive to the next reference (2403.02574 sec 3.2.2).
5. The guidance text explicitly asks the model to relate the new reference to the target paper and to the references already in the draft (2403.02574 sec 3.2.1).
6. The values of n_s, n_c and n_v are never given in the paper.
7. The tree depth equals the number of references, so cost is linear in references and quadratic in beam parameters (2403.02574 sec 3.2.3).

### Model calls and cost

1. GPT-3.5-turbo-1106 writes, GPT-4-turbo-preview evaluates, and GPT-4 was avoided as the writer on cost grounds (2403.02574 sec 5.1).
2. No token counts, dollar cost, wall-clock time or LLM call count are reported.

### The result that matters

1. ChatCite on GPT-3.5 scores G-Score 4.0642 against GPT-4 zero-shot at 3.5076, so the loop beats a two-tier-larger model (2403.02574 sec 5.1, Table 1).
2. ROUGE actively disagrees, GPT-4 zero-shot wins ROUGE-1 30.02 to 25.30, which is why they built G-Score (2403.02574 sec 5.1, Table 1).
3. This is the strongest published evidence that structure recovers most of a model-size gap on this task.

### What would degrade on a 26B model

1. The reflective evaluator is the same model family as the writer, so a 26B would be voting on its own output with no stronger signal in the loop (2403.02574 sec 3.2.2).

---

## 9. OpenScholar (2411.14199)

### Pipeline

1. The datastore is peS2o v3, 45M papers split into 250-word passages with the title prepended, 234M passages total (2411.14199 sec 2.1).
2. Retrieval has three arms: a trained bi-encoder over the datastore, Semantic Scholar keyword search ranked by citation count, and a You.com web search (2411.14199 sec 2.1).
3. The bi-encoder is Contriever continually pretrained on peS2o, 110M parameters (2411.14199 sec 2.1, sec 4.1).
4. A 340M cross-encoder reranker, a BGE-reranker fine-tuned on Llama-3-70B relevance labels, cuts the pool to top N (2411.14199 sec 2.1, sec 4.1).
5. Meta-filtering caps each paper at 3 passages and folds normalized citation counts into the reranker score (2411.14199 sec 2.1).
6. The generator writes y0 with citation markers, then writes at most 3 natural-language feedback sentences about its own draft (2411.14199 sec 2.2).
7. A feedback sentence that names missing content also emits a retrieval query, so the loop can pull new passages mid-generation (2411.14199 sec 2.2).
8. Feedback is applied one at a time and the output is not regenerated from scratch each round, explicitly for latency (2411.14199 sec 2.2, footnote 4).
9. The last step is citation verification, where the model checks that every citation-worthy statement has support and post-hoc inserts missing citations (2411.14199 sec 2.2).
10. Top N is 5 passages for single-paper tasks and 10 for multi-paper tasks (2411.14199 sec 4.1).
11. Generation is capped at 3,000 tokens and feedback at 1,000 tokens, so the output is an answer and not a survey (2411.14199 sec 4.1).
12. The 8B model is trained on 130k instances distilled from the pipeline's own outputs, so the loop is compiled into the weights (2411.14199 sec 2.3, sec 4.1).

### Model calls and cost

| model | USD per query |
| --- | --- |
| OpenScholar-8B | 0.01 |
| OpenScholar-GPT4o | 0.05 |
| PaperQA2 | 0.3 to 2.3 |
| Perplexity Pro | 0.002 |

1. Costs are per query for a ~3,000-token answer, not per survey (2411.14199 sec 4.2, Table 2).
2. No wall-clock time is reported.

### The two measurements we should design around

1. GPT-4o and Llama without retrieval fabricate 78 to 98 percent of the papers they cite, and it is worse in biomedicine (2411.14199 sec 4.2, Table 3).
2. Ablating self-feedback costs GPT-4o 8.5 citation points, 39.5 to 31.0, but the trained 8B goes up, 47.9 to 50.2 (2411.14199 sec 4.3, Figure 4a).
3. Ablating the reranker is the single most damaging removal for both, 47.9 to 28.2 on the 8B and 39.5 to 22.9 on GPT-4o (2411.14199 sec 4.3, Figure 4a).
4. Untrained Llama-3.1-8B citation F1 collapses toward 10 as passages grow past 10, while the trained 8B and Llama-70B hold near 40 (2411.14199 sec 4.3).
5. So a small model's citation accuracy is a function of how many passages you show it, and training fixes that where prompting does not.

### What would degrade on a 26B model

1. The citation-F1 collapse above is the direct warning: a 26B given a large pool without task training will drop citations even when the passages are right there.
2. The feedback ablation says a self-critique loop is not the fix for a small model, retrieval quality and training are.
3. Experts judged the 8B output less organized and less fluent than the GPT-4o output even at matched correctness (2411.14199 sec 5.2).

---

## 10. Instruct LLMs to Generate Scientific Literature Surveys (2408.07884)

### Pipeline

| step | call | context |
| --- | --- | --- |
| 1 | title | subject plus the full reference list |
| 2 | 6 to 10 section headings | follow-up turn, keeps step 1 memory |
| 3 | abstract | subject, title, outline |
| 4 | pick refs per section | subject, title, outline, full reference list |
| 5 | 3 to 5 subsection headings | title, outline, that section's refs |
| 6 | subsection content | title, full outline, that section's refs |

1. Steps 1 to 3 are a single conversation with retained memory, so the outline is built strictly sequentially (2408.07884 sec 3.2).
2. Reference selection is done by the LLM reading the whole reference list once per section, not by embedding retrieval (2408.07884 Step 4).
3. They give the explicit reason for per-section reference subsets: cost, and stopping every section from looking the same (2408.07884 Step 4).
4. Only titles are used, never reference content, because the task rules forbade it (2408.07884 sec 3.1).
5. There is no revision loop, but there is a format retry: if a required marker is missing, the same prompt is reissued with a corrective prefix (2408.07884 Step 1).
6. Heading count is validated numerically, and regenerated only if outside 3 to 25 (2408.07884 Step 2).
7. The subsection title is repeated several times inside the writing prompt because the model loses focus in a long prompt (2408.07884 Step 6).

### Model calls and cost

1. Calls per survey are 3 plus 2 x sections plus subsections, and with 6 to 10 sections at 3 to 5 subsections each that is roughly 33 to 73 calls (derived from 2408.07884 sec 3.2, not stated as a count).
2. All 200 test surveys cost 20.86 RMB, about 0.10 RMB per survey, on Qwen-long (2408.07884 sec 4.2).
3. That is the cheapest system in this set by two orders of magnitude, and it is also the least grounded.
4. Reference lists over the context limit are simply truncated to the first 80 to 100 entries (2408.07884 sec 4.2).
5. No wall-clock time is reported.

### What this tells us

1. Soft heading recall of 95.84 shows outline structure is easy, their human score of 63.78 shows content is not (2408.07884 sec 4.4).
2. A pipeline that never reads a single abstract still gets 95.84 heading recall, so heading-level metrics prove almost nothing.

---

## Cross-system comparison

### Outline

| id | how the outline is produced | parallel or sequential | revision of the outline |
| --- | --- | --- | --- |
| 2406.10252 | one outline per 30k-token abstract chunk, then merged, fixed at 8 sections | parallel chunks | none |
| 2503.04629 | retrieved human survey outlines plus retrieved papers, two levels, each heading gets a query | recursive per section | none |
| 2502.14776 | level 1 from parametric knowledge, level 2 from per-reference hints, then deduplicated | sequential | one dedup pass |
| 2504.08762 | agglomerative clustering of per-paper descriptions, cluster names become sections | n/a | the user edits it |
| 2506.12689 | template picked by intent, then a 3-model ensemble merged | parallel candidates | up to 2 reflection rounds |
| 2402.14207 | parametric draft, then refined against 6 simulated conversations | sequential | one refine pass |
| 2504.05732 | per-cluster skeletons merged, then entropy-guided convolution and best-of-N | parallel then iterative | 6 conv layers plus 3 best-of-3 |
| 2403.02574 | none, the draft grows one reference at a time | sequential | n/a |
| 2411.14199 | none, it is a single answer | n/a | n/a |
| 2408.07884 | 6 to 10 headings from the title in one call | sequential | count check only |

### Section writing

| id | parallel | context given to one section call | revision loop | trigger |
| --- | --- | --- | --- | --- |
| 2406.10252 | yes | outline, 60 papers x 1,500 tokens, name, description | 2 passes, citations then coherence | unconditional |
| 2503.04629 | yes | outline, memory M_i, 60 reranked papers | 1 pass over the concatenation | unconditional |
| 2502.14776 | partly, sees other subsections | outline, hints, attribute trees | RAG rewrite per paragraph | unconditional |
| 2504.08762 | yes within a section | subsection title, retrieved chunks | none | n/a |
| 2506.12689 | no, section at a time | section spec, retrieved papers, titles, abstracts, full texts | up to 2 rounds, can re-retrieve | non-empty critique |
| 2402.14207 | yes | section title plus all subsection headings, retrieved from R | dedup over the whole article | unconditional |
| 2504.05732 | leaves parallel, parents after children | skeleton node, per-paper digests, children's text | none at write time | n/a |
| 2403.02574 | no, one reference per turn | previous draft, target key elements, one reference | beam plus vote, every turn | every turn |
| 2411.14199 | n/a, one answer | 5 or 10 passages | up to 3 feedback items, can re-retrieve | model-authored feedback |
| 2408.07884 | independent per subsection | title, full outline, that section's refs | none | n/a |

### Reference list assembly

| id | how the bibliography is produced | can it cite something that does not exist |
| --- | --- | --- |
| 2406.10252 | generated titles embedded and snapped to the nearest real title | no, but it can snap to the wrong paper |
| 2503.04629 | cited from the retrieved set, same scheme as AutoSurvey | same |
| 2502.14776 | post-hoc RAG rewrite adds and removes citations per paragraph | no |
| 2504.08762 | post-hoc, per sentence, cosine over reference chunks above an adaptive threshold | no |
| 2506.12689 | Refiner dedupes and renumbers after writing | not stated |
| 2402.14207 | citation markers into R, written inline | no |
| 2504.05732 | BIBKEYs carried on skeleton nodes into the digests | no |
| 2403.02574 | references named in the source dataset | no |
| 2411.14199 | inline markers, then a post-hoc verification and insertion pass | no |
| 2408.07884 | bracketed indices into the given list | yes, an index can be invented |

### Reported cost and time

| id | tokens per report | money | wall clock | model |
| --- | --- | --- | --- | --- |
| 2406.10252 | 3,009.7K in, 112.9K out at 32k | $0.89 haiku, $33.48 GPT-4 | 73.59 per hour claimed, 3 min claimed | Claude-3-Haiku |
| 2503.04629 | 2.37M in, 0.13M out at 64k | $0.43 GPT-4o-mini, $0.37 DeepSeek-v3 | ~10 min | Claude-3-Haiku or GPT-4o-mini |
| 2502.14776 | not reported | not reported | not reported | GPT-4o |
| 2504.08762 | not reported | not reported | 2,077.8 s | qwen2.5-72b-instruct |
| 2506.12689 | not reported | not reported | not reported | Qwen3-32B |
| 2402.14207 | not reported | not reported | not reported | gpt-3.5 plus gpt-4 |
| 2504.05732 | not reported, input up to 4.66M | not reported | not reported | Gemini-2.0-flash-thinking |
| 2403.02574 | not reported | not reported | not reported | GPT-3.5 writer, GPT-4 judge |
| 2411.14199 | not reported | $0.01 to $0.05 per query | not reported | Llama-3.1-8B trained, or GPT-4o |
| 2408.07884 | not reported | 0.10 RMB | not reported | Qwen-long |

1. Not one of the ten reports an LLM call count per report.
2. Only 2503.04629 and 2504.08762 report a real wall-clock number, 10 minutes and 35 minutes.

### Reference coverage against a human reference set

| system | metric | value | source |
| --- | --- | --- | --- |
| human survey | reference coverage | 0.6294 | 2503.04629 Table 1 |
| SurveyForge, GPT-4o-mini | reference coverage | 0.4236 | 2503.04629 Table 1 |
| SurveyForge, retrieved pool | input coverage | 0.2231 | 2503.04629 Table 1 |
| AutoSurvey | reference coverage | 0.2341 | 2503.04629 Table 1 |
| AutoSurvey, retrieved pool | input coverage | 0.1153 | 2503.04629 Table 1 |
| SciSage | reference F1 | 0.46 | 2506.12689 Table 4 |
| AutoSurvey | reference F1 | 0.14 | 2506.12689 Table 4 |
| OpenScholar | reference F1 | 0.061 | 2506.12689 Table 4 |
| LLMxMapReduce-V2 | reference F1 | 0.017 | 2506.12689 Table 4 |

1. The two benchmarks disagree on AutoSurvey by a factor of about 1.7, so these numbers are comparable only within a column.
2. Every published retrieval-based system finds well under half the references a human would cite, and most find under a quarter.

### What each system does only because it lacks a citation graph or full text

| id | the workaround | what replaces it for us |
| --- | --- | --- |
| 2406.10252 | snap generated titles to nearest real title | hand the writer arxiv ids and verify them |
| 2406.10252 | truncate every paper to its first 1,500 tokens | read the sections that matter |
| 2503.04629 | keep a separate 20k-outline database to learn structure | read the section trees of real surveys in our own corpus |
| 2503.04629 | rerank by a scalar citation count | rank by graph position, PPR, in-degree, intent-labeled edges |
| 2502.14776 | keyword expansion loop to grow coverage | traverse citation edges |
| 2502.14776 | Google Scholar crawler for anything the dump lacks | 3.1M papers already local |
| 2504.08762 | MinerU PDF parsing dominates a 35-minute run | HTML already parsed on disk |
| 2504.08762 | 45.2 references per topic | pool sizes of hundreds |
| 2402.14207 | simulate 6 personas x 5 turns to discover subtopics | the topic tree already partitions the corpus |
| 2402.14207 | rule-based trust filter on web results | every source is an arXiv paper |
| 2411.14199 | web search arm plus Semantic Scholar arm | one local store |
| 2411.14199 | cap each paper at 3 passages of 250 words | whole papers available |
| 2408.07884 | truncate the reference list to 80 to 100 | no list to truncate |

### Evidence about small models

| id | evidence | direction |
| --- | --- | --- |
| 2406.10252 | Claude-3-Haiku 4.58 avg vs GPT-4 4.70, citation recall higher on haiku | small models fine |
| 2503.04629 | DeepSeek-v3 beats GPT-4o-mini on every metric | open models fine |
| 2504.08762 | fill-in-the-blanks outline built specifically for weaker LLMs | structure compensates |
| 2403.02574 | GPT-3.5 in the loop beats GPT-4 zero-shot on G-Score | structure compensates |
| 2506.12689 | whole comparison runs on Qwen3-32B, reflection worth 8 to 10 points | 32B handles a reflection loop |
| 2402.14207 | gpt-3.5 is not faithful to sources when writing with citations, so gpt-4 writes | small models fail at citing |
| 2411.14199 | untrained 8B citation F1 falls toward 10 as passages grow past 10 | small models fail at citing |
| 2411.14199 | self-feedback helps GPT-4o by 8.5 cite points, does not help the trained 8B | critique loops need scale |
| 2411.14199 | experts call 8B output less organized and less fluent at equal correctness | small models write worse prose |

1. The split is consistent: a 26B is fine at planning, extraction and comparison, and unreliable at attaching the right citation to the right sentence when the pool is large.
2. Every system that fixed citations at scale did it mechanically after generation, not by asking the writer to be careful.

---

## The design choices that recur in every system

1. **Plan the document structure in its own stage, before any section is written.**
2. Eight of the ten build an explicit outline or skeleton first, the exceptions being ChatCite and OpenScholar, which produce a single passage and never plan.
3. Four of those eight pass the complete outline into every section-writing call, so a section knows what its neighbors will cover (2406.10252 Appendix F, 2502.14776 sec 3.2.2, 2506.12689 sec 3.2, 2408.07884 Step 6).
4. The other four pass only the local node, its queries and its retrieved papers (2503.04629 sec 3.2.1, 2504.08762 Appendix A.2, 2402.14207 sec 3.4, 2504.05732 sec 3.3).
5. STORM measured the counterfactual: removing the outline stage degrades every metric (2402.14207 sec 5.2).

6. **Compress every paper into a fixed schema before writing, never pass raw text.**
7. SurveyX uses four typed AttributeTree templates and MapReduce-V2 uses skeleton-dictated digests (2502.14776 sec 3.1.2, 2504.05732 sec 3.1).
8. ChatCite uses seven fixed questions and OpenScholar uses 250-word passages capped at 3 per paper (2403.02574 sec 3.1, 2411.14199 sec 2.1).
9. SurveyX measured the counterfactual: swapping the attribute tree for full text costs 23 points of citation F1 (2502.14776 sec 4.3, Table 2).
10. This is the load-bearing one for us, because our advantage is full text and the literature says full text is a liability until it is typed.

11. **Fix citations mechanically after generation, in a pass separate from writing.**
12. AutoSurvey runs a citation reflection prompt and SurveyX runs a RAG rewrite over every paragraph (2406.10252 Appendix F, 2502.14776 sec 3.2.3).
13. InteractiveSurvey attaches citations by cosine threshold with no writer involvement, and OpenScholar verifies and inserts post hoc (2504.08762 Appendix C, 2411.14199 sec 2.2).
14. SurveyX measured the counterfactual: removing that pass costs 26 points of citation F1, the largest single ablation in any of these papers (2502.14776 sec 4.3, Table 2).

15. A fourth pattern is common but not universal: write sections independently, then pay for it with one deduplication pass over the concatenation (2406.10252 sec 2, 2503.04629 sec 3.2.2, 2402.14207 sec 3.4, 2502.14776 sec 3.2.3).
16. The two systems that write sequentially, ChatCite and SciSage, are also the two that report the strongest comparative-analysis behavior, which suggests parallelism costs synthesis (2403.02574 sec 3.2.1, 2506.12689 sec 6.2.1).

---

## The single biggest thing our access lets us do differently

1. Every one of these systems selects its references by text similarity to a query, and every one of them recovers under half the references a human would have cited (2503.04629 Table 1, 2506.12689 Table 4).
2. The reason is stated in SurveyForge's own limitations: without structure they cannot trace methodological evolution and default to mechanical reference listing (2503.04629 Limitations).
3. We can select by graph position instead of by text similarity, which means a foundational ancestor is reachable even when its vocabulary has shifted away from the query, the case that text retrieval structurally cannot solve.
4. We can then do the thing none of them can attempt: verify a claim against the cited paper's own text rather than against the 250-word snippet that was retrieved.
5. STORM's expert editors found the dominant failure was not fabricated facts but unverifiable connections drawn between two real retrieved facts (2402.14207 sec 6).
6. A snippet-based system cannot detect that failure because the snippet does not contain the claim's context, and we hold the whole paper.
7. Concretely, our citation-intent labels on 72.8M resolved edges make it checkable whether paper A actually extends, uses or contradicts paper B, which every system in this set asserts from prose alone.
8. The second-order consequence is speed: InteractiveSurvey spends most of a 35-minute run parsing PDFs it just downloaded, and that entire stage is already done for us (2504.08762 sec 4.2).

## Cautions to carry forward

1. Do not hand a 26B writer raw full text, hand it typed extractions, because SurveyX measured a 23-point citation F1 loss from exactly that substitution (2502.14776 Table 2).
2. Do not rely on a self-critique loop to fix citations on a small model, because OpenScholar measured that it helps GPT-4o and does not help a trained 8B (2411.14199 Figure 4a).
3. Do not grow the pool shown to one writing call, because untrained-8B citation F1 falls toward 10 past 10 passages while a 70B holds (2411.14199 sec 4.3).
4. Do not report heading-level structure metrics as evidence, because a pipeline that reads no abstracts scores 95.84 soft heading recall (2408.07884 sec 4.4).
5. Do not compare a reference F1 across the two benchmarks, because they rank AutoSurvey at 0.2341 and 0.14 for the same system (2503.04629 Table 1, 2506.12689 Table 4).
