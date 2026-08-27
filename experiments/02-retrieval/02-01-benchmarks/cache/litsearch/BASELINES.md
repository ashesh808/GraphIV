# Their baseline methods, and what it costs to run each one here

"Local" means one 3090 plus the llama-server already in this stack, with no paid API and no
commercial search engine.
Every file path below is under `raw/`.

## LitSearch retrievers

All five share `code_eval_retrieval_kv_store.py`: encode all 64183 documents once, encode the
query, take the top-k by cosine over a dense in-memory matrix.
There is no ANN index and no sharding.
The default indexed field is `f"Title: {title}\nAbstract: {abstract}"`, 134 words on average.

| arm | checkpoint | prompt or instruction | local |
| --- | --- | --- | --- |
| BM25 | `rank_bm25.BM25Okapi`, default k1 and b | none | yes |
| GTR | `sentence-transformers/gtr-t5-large` | none, raw text both sides | yes |
| Instructor | `hkunlp/instructor-xl` | asymmetric, see below | yes |
| E5 | `intfloat/e5-large-v2` | `"query: "` and `"passage: "` | yes |
| GritLM | `GritLM/GritLM-7B` | `"<|embed|>\n"` for keys, `"<|user|>\n{instruction}\n<|embed|>\n"` for queries | tight on 24 GB |

BM25 tokenization is exactly `nltk.word_tokenize` on the lowercased string, then NLTK English
stopword removal, then `PorterStemmer`.
Reproducing their BM25 number requires that exact chain, since a different analyzer moves BM25
by several points.

Instructor instructions for the `title_abstract` key:

- query: `Represent the research question for retrieving relevant research paper abstracts:`
- key: `Represent the title and abstract of the research paper for retrieval:`

GritLM instruction for the `title_abstract` key:
`Given a research query, retrieve the title and abstract of the relevant research paper`

Encoding batch sizes are 256 for GTR, E5 and GritLM, 128 for Instructor.
E5 is cast to bfloat16, and every index is stored as float16.
Context limits are 512 tokens for GTR, Instructor and E5, and 2048 for GritLM.

## LitSearch rerankers

| arm | what it does | local |
| --- | --- | --- |
| GPT-4 reranking | RankGPT permutation over the top-100 | no, needs GPT-4 |
| GPT-4 one-hop | expand top-50 by their outgoing citations to 200, then rerank | no, needs GPT-4 |

The reranker is `gpt-4-1106-preview` through Azure OpenAI.
It is not a sliding window: `rank_start=0` and `rank_end=100`, so all 100 documents go into one
prompt as alternating user and assistant turns, each truncated to 300 words.
On a context-overflow exception it drops `(rank_end - rank_start) // 5` documents and retries,
down to a floor of half the original count, then gives up and keeps the original order.
The output is parsed by stripping every non-digit, so `[3] > [1] > [2]` becomes `3 1 2`, and any
identifier the model omitted is appended in its original order.

One-hop (`code_eval_onehop_get_onehop_union.py`) walks the top-50 retrieved ids in rank order,
appends each one's `citations` list, and stops at 200 documents total.
The `citations` field is already in `corpus_clean` and is restricted to targets inside the 64183
corpus, so this is a closed-corpus one-hop expansion and needs no external graph.

A local substitute for the reranker is a listwise prompt against `llama-router`, but it is a
substitute and not a reproduction, so its number cannot be put in the same column as theirs.

## PaSa

PaSa is two fine-tuned Qwen2.5-7B models plus a web search tool.

| component | checkpoint | role |
| --- | --- | --- |
| Crawler | `bytedance-research/pasa-7b-crawler` | emits `[Search]`, `[Expand]`, `[Stop]` actions |
| Selector | `bytedance-research/pasa-7b-selector` | scores one paper against the query |

Both weights are ungated on HuggingFace, unlike the dataset.

### The Selector

Prompted with the query plus the paper title and abstract, asked for
`Decision: True/False\nReason:...`, with the decision token emitted first.
The score is not parsed text: `code_models.py::infer_score` generates exactly one token with
`output_scores=True` and reads `softmax(logits)[token_id("True")]`.
The keep threshold is `> 0.5`, and the same probability is the ranking key for recall@k.
This is reproducible against any local server that returns logprobs over the first token.

### The Crawler loop

Defaults from `code_run_paper_agent.py`: `expand_layers=2`, `search_queries=5`,
`search_papers=10` per query, `expand_papers=20` per layer, 20 threads.

1. Prompt `generate_query` on the user query, parse `[Search]...` spans, keep the first 5.
2. For each, call Google through serper.dev with `f"{query} before:{end_date} site:arxiv.org"`,
   and regex arXiv ids out of the result links.
3. Fetch title, abstract and sections per id from a local paper database, falling back to the
   arXiv API and ar5iv.
4. Score every fetched paper with the Selector and push it onto the queue.
5. For each queued paper, prompt `select_section` with the section names, and add every paper
   cited in the chosen subsections to the queue.
6. Repeat step 5 for `expand_layers` layers.

`end_date` is the source paper's publication date minus 7 days.
The reward shaping used in training is `alpha=1.5`, with a cost of 0.1 per `[Search]` and per
`[Expand]`, which is visible in `code_metrics.py` as the `total_score` accumulator.

### What is runnable here

| piece | local | blocker |
| --- | --- | --- |
| Selector | yes | 7B at bf16 fits on a 3090, and the weights are ungated |
| Crawler weights | yes | same |
| `[Search]` | **no** | needs a paid serper.dev key, and Google is the retrieval corpus |
| `[Expand]` | partial | ar5iv is rate-limited, but our `citation` table already holds 177M edges |
| AutoScholarQuery, RealScholarQuery | **no** | gated dataset, see PROTOCOL.md |

`[Search]` is the load-bearing blocker.
Substituting our own vector search for Google does not reproduce PaSa, it produces a different
system that happens to share PaSa's agent loop, because Google over all of arXiv and a pgvector
KNN over our corpus are different retrieval functions.
That substitution is worth running as **our** ablation, and its number cannot go in a column
headed PaSa-7b.

## Summary of reimplementation cost

| baseline | reproducible offline | effort |
| --- | --- | --- |
| BM25 on LitSearch | yes, exactly | low, the analyzer chain is fully specified |
| GTR, E5, Instructor on LitSearch | yes, exactly | low, all three are small and public |
| GritLM-7B on LitSearch | yes | 7B encoder over 64183 docs, one pass |
| GPT-4 rerank, GPT-4 one-hop | no | needs GPT-4, only a local stand-in is possible |
| PaSa Selector | yes | ungated 7B, single-token logprob |
| PaSa Crawler end to end | no | Google search API is the corpus |
| Google, Google Scholar, ChatGPT, GPT-o1 arms | no | commercial, and partly hand-run in the paper |
