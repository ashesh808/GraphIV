# kb

Whether a per-question knowledge base can be built from the pool, on local hardware, and whether
it answers a question with a pointer to where in the paper the answer sits.

One topic throughout: `graph retrieval-augmented generation`. Gemma-4-26B for reading, the 131k
instance for answering, nomic for embedding, no other model.

## TLDR

1. The pipeline works end to end and the whole thing runs in minutes on one box.
2. Node extraction from abstracts gives good entities and useless claims, because an abstract's
   claims are advertising.
3. The same extraction from results sections gives claims with numbers in them, and 12.5% of the
   quotes are fabricated and get dropped by a string check rather than by a model.
4. Four gap detectors were tried and one works. The three failures all fail the same way, by
   ranking generic nodes to the top.
5. Q&A answers with a section and a verbatim quote, and across 15 spans none were invented.
6. Papers the five surveys "missed" are mostly famous adjacent work they scoped out on purpose.
   The valuable ones did not exist when the surveys were written, so that goal is the frontier
   goal wearing a different hat.

## Pipeline, and what each stage costs

| stage | in | out | seconds |
| --- | --- | --- | --- |
| pool | one question | 1,000 papers, 38,162 intent typed edges | 37 |
| entity extraction | 1,000 abstracts | 7,593 nodes, 35,581 edges | 1,060 |
| claim extraction | 30 papers, 62 results sections | 154 grounded claims | 104 |
| rationale extraction | 30 papers, 53 method sections | 179 grounded rationales | 181 |
| relation extraction | 154 claims | 144 typed relations | 24 |
| one answer | a question | answer plus spans | 2.5 |

The pool is 10,834 candidates cut to 1,000. Claim and rationale extraction run at 3.5s and 6.0s
a paper, so the full 1,000 would be 58 and 100 minutes.

## Node merging, by type

| type | names | nodes | shared by 2+ papers |
| --- | --- | --- | --- |
| dataset | 588 | 588 | 98% |
| technique | 1,979 | 1,979 | 11% |
| task | 1,467 | 1,467 | 17% |

| merge rule | technique names to nodes | what it does wrong |
| --- | --- | --- |
| embedding, 0.80 | 104 -> 51 | GraphRAG, LightRAG and PathRAG become one node |
| embedding, 0.90 | 104 -> 84 | GPT-3 and GPT-4 become one node |
| embedding, 0.94 | 104 -> 96 | HippoRAG and HippoRAG 2 become one node |
| string form | 106 -> 97 | nothing, but it only catches spelling variants |

## Claim quality, abstract against full text

| source | example claim |
| --- | --- |
| abstract | LightRAG improves retrieval accuracy and efficiency. |
| abstract | Graph structures enhance contextual relevance. |
| results section | LightRAG won 56.38% of Agriculture comparisons against GraphRAG's 43.62%. |
| results section | G-Retriever + LoRA beats standard LoRA by 5.62% on SceneGraphs and 13.56% on WebQSP. |
| results section | Graph based retrieval cut average tokens 83% on SceneGraphs and 99% on WebQSP. |

| extraction | records kept | quotes not in the section |
| --- | --- | --- |
| claims, results sections | 154 | 22 (12.5%) |
| rationales, method sections | 179 | 26 (12.7%) |

## Gap detectors

| detector | verdict | what it returns |
| --- | --- | --- |
| untried pairing | fails | Knowledge Graph x HotpotQA, Transformer x MMLU |
| islands | fails | pairs that are co-cited, sharing only generic entities |
| orphan claim | fails | Transformer, BERT, CLIP, GPT-3 |
| cold entity | works | GCN, Seq2Seq, Late Interaction, BART, Dual Encoders, kNN-LM |
| echoed claim, full text | fails | "achieves state of the art performance" said twice |

Removing nodes named by more than 10% of the pool changed none of the failures, because the
offending nodes sit at 2 to 3%.

## The relation graph read as a tournament

| relation | count |
| --- | --- |
| outperforms | 93 |
| improves | 26 |
| reduces | 9 |
| matches | 5 |
| fails_at | 5 |
| requires | 4 |
| enables | 2 |

| paper | relations that are its own win |
| --- | --- |
| 2405.20139 | 13 of 14 |
| 2405.16506 | 9 of 9 |
| 2410.20724 | 9 of 9 |
| 2401.18059 | 8 of 8 |

| system | all edges | third party edges only |
| --- | --- | --- |
| HippoRAG | 5W 2L | 1W 2L |
| SubgraphRAG | 7W 0L | 7W 0L |
| RoG | 0W 6L | 0W 4L |
| one-step retrieval | 0W 6L | 0W 6L |

At 200 papers: 1,094 claims to 1,059 relations in 195s, 1,080 endpoints, 336 in two or more edges.

| papers | relations | pairs claimed in both directions |
| --- | --- | --- |
| 30 | 144 | 0 |
| 200 | 1,059 | 7 |

All 7 come from one paper rather than from two papers disagreeing, and 5 of them are metric
tradeoffs the paper reported honestly.

| pair | one direction | the other |
| --- | --- | --- |
| GraphRAG vs VectorRAG | faithfulness | context recall, 0.15 |
| GraphRAG vs HybridRAG | context precision, 0.17 | answer relevancy, 0.07 |
| ES IR vs KG IR | recall at large sets | precision and recall overall |
| larger vs smaller blocks | recall and precision | BLEU |
| GRPO vs Reinforce++ | response length | in-domain learning efficiency |

The other 2, GRPO against PPO and CCNet against Wikipedia, cite the identical quote for both
directions, so they are extraction errors rather than tradeoffs. The `metric` field separates the
two cases and the clash test ignored it.

## Answers, and whether their spans exist

| question | ids used | spans | invented |
| --- | --- | --- | --- |
| Why did the authors of LightRAG build it the way they did? | 1 | 5 | 0 |
| Why build a community summary instead of retrieving chunks? | 2 | 3 | 0 |
| What is the strongest evidence that graph RAG does not help? | 1 | 3 | 0 |
| Which system should I use if I care about token cost? | 3 | 4 | 0 |

The same question against results sections alone returned "the evidence does not answer this",
which is why rationale extraction exists.

## Papers the five surveys did not cite, top 120 of the pool

| set | n | citations p50 |
| --- | --- | --- |
| cited by at least one survey | 67 | 311 |
| existed, cited by none | 26 | 224 |
| appeared after the newest survey | 22 | 39 |

| the 22, by hand | count |
| --- | --- |
| graph RAG advances: PathRAG, HyperGraphRAG, GFM-RAG, NodeRAG, ArchRAG, E2GraphRAG, LinearRAG, HopRAG, Graph-R1 | 15 |
| direct evaluations of the premise: RAG vs GraphRAG, When to use Graphs in RAG, In-depth Analysis, GraphRAG-Bench | 4 |
| off topic hubs: DeepSeek-R1, Qwen3 | 2 |
| memory: From RAG to Memory | 1 |

## Model written extra queries, the long mode premise

Answer key is the 533 references of the five RAG surveys.

| run | @50 | @100 | @200 | @500 | @1000 |
| --- | --- | --- | --- | --- | --- |
| base, one query | 0.062 | 0.116 | 0.223 | 0.432 | 0.632 |
| 8 model queries fused by RRF | 0.060 | 0.120 | 0.210 | 0.402 | 0.570 |
| base plus the 8, fused | 0.060 | 0.120 | 0.216 | 0.415 | 0.587 |

| pool | papers | share of the key inside it |
| --- | --- | --- |
| base alone | 2,000 | 0.856 |
| union of the 8 sub pools | 7,627 | 0.919 |

Expansion widens the pool and worsens the ranking, since RRF weights all eight queries the same.

## The model writing the traversal

A written query is `{subject, relation, object, metric, hops, either_side, rank_by}` over the
1,059 relation edges, executed by 40 lines of python.

| question | first form | with either_side and rank_by |
| --- | --- | --- |
| What beats HippoRAG and on what metric? | answered | answered |
| Which systems are the baseline everything compares against? | wrong relation, empty | answered |
| What does anyone report graph RAG is worse at? | wrong direction, 0 edges | answered |
| What did GraphRAG lose on, and to what? | partial | answered |

Adding the two fields broke the first question until ranking was made to yield whenever the query
also names a thing, since the model sets `rank_by` even on a question that is a plain match.

Example answer, question one: KAG beats IRCoT + HippoRAG by 11.5 EM on HotpotQA, 19.8 on
2WikiMultiHopQA and 10.5 on MuSiQue; LinearRAG by 3.95 average accuracy; HopRAG by 3.08;
SiReRAG by 8.3 F1. Retrieval alone cannot answer this at any budget.

# Session two

## Extra queries, resolved

The premise was right and RRF was the problem. Answer key is the 533 references of the five
RAG surveys, and the union run gathers 7,700 candidates from nine questions then lets the
original question rank them through the same four channel fuse.

| run | @50 | @100 | @200 | @500 | @1000 | @2000 |
| --- | --- | --- | --- | --- | --- | --- |
| base only | 0.062 | 0.116 | 0.223 | 0.432 | 0.632 | 0.856 |
| RRF over 8 sub queries | 0.060 | 0.120 | 0.210 | 0.402 | 0.570 | 0.767 |
| RRF over base and 8 | 0.060 | 0.120 | 0.216 | 0.415 | 0.587 | 0.773 |
| union, ranked by the original question | 0.077 | 0.131 | 0.238 | 0.469 | 0.657 | 0.874 |

Better at every budget, so it is a Pareto win. Cost is 37 seconds against about 5 minutes,
which is the quick and long modes.

## Which papers earn a full text read

150 of 1,000, scored by whether the resulting comparison graph is connected.

| sampler | papers with html | claims | edges | nodes | largest component | with a number |
| --- | --- | --- | --- | --- | --- | --- |
| topk | 137 | 783 | 781 | 809 | 331 | 390 |
| leyline | 139 | 860 | 807 | 875 | 313 | 383 |
| random | 136 | 816 | 763 | 872 | 229 | 364 |
| spread | 109 | 604 | 559 | 660 | 77 | 237 |

LeyLine yields the most claims and a less connected graph, since walking a lineage spreads the
sample across time instead of concentrating on a cohort that compares itself. Spreading over the
pool on purpose is the worst by a wide margin, and it also loses papers, since older ones have
no ar5iv html.

## Neo4j

The store already held neo4j 2026.07.0, so nothing recompiled. An ephemeral instance runs on
bolt 7690 and http 7477 with its own data directory, unrelated to the one already listening on
7687.

| load | value |
| --- | --- |
| seconds | 3.1 |
| Paper, System, Entity nodes | 1,000, 1,080, 555 |
| CITES, MENTIONS, COMPARED, REPORTS | 38,162, 3,101, 1,059, 537 |

## The schema the model proposes, by field

| field | node types |
| --- | --- |
| graph RAG | Paper, Method, Task, Benchmark, Component, Challenge |
| tabular foundation models | Paper, Model, Task, Benchmark, Technique, Limitation |

Asked without further instruction it proposed `(Paper)-[:CONTRASTS]->(Paper)`, which cannot say
which one won. One line requiring a relation whose subject is the winner produced
`(Method)-[:OUTPERFORMS]->(Method)` and `(Model)-[:OUTPERFORMS]->(Model)`.

## Content level against document level

The same 60 papers, read whole rather than by their results sections, against the schema the
model proposed for this question.

| | abstract entities | content triples |
| --- | --- | --- |
| unit | a name a paper mentions | a typed triple with a quote |
| papers | 1,000 | 60 |
| records | 7,593 nodes | 1,847 triples |
| method nodes shared by 2+ papers | 11% | GraphRAG 163, RAG 90, LightRAG 49, HippoRAG 49 |

Full text names the same systems over and over, so the merge problem that made abstract level
techniques 11% shared mostly goes away.

| triples rejected | why |
| --- | --- |
| 347 | the quote is not in the section |
| 216 | the endpoint types do not match the relation the schema declares |
| 5 | the reply did not parse |

| label | nodes | relation | edges |
| --- | --- | --- | --- |
| Component | 367 | UTILIZES | 581 |
| Method | 357 | APPLIES_TO | 319 |
| Challenge | 222 | ADDRESSES | 312 |
| Task | 150 | PROPOSES | 276 |
| Benchmark | 68 | EVALUATED_ON | 185 |
| Paper | 63 | OUTPERFORMS | 174 |

## Cypher written by the model against its own schema

| question | rows | verdict |
| --- | --- | --- |
| Which methods outperform GraphRAG, and on what? | 14 | five sources with numbers |
| Which methods address hallucination? | 56 | 16 methods, answer's first sentence misreads a UNION |
| Which components are used by methods evaluated on MuSiQue? | 25 | query correct, but it did not return the benchmark it matched, so the reader could not see it |
| Find a method that beats something that beats HippoRAG | 0 | genuine sparsity, no two hop chain exists at 174 edges |
| What is evaluated on HotpotQA and what does it use? | 25 | three methods with their components |

Two prompt lines fix the two failures that are not sparsity: return every node the question
named, and write one MATCH rather than a UNION.

The first answer, unedited: LightRAG outperforms GraphRAG at 56.38% Agriculture, 54.02% CS,
54.30% Legal and 48.14% Mix [2410.05779]; PathRAG averages 60.44% [2502.14902]; HyperGraphRAG
wins on factuality, comprehensiveness, diversity and empowerment [2503.21322]; HiRAG 64.1
against 35.9 on Mix [2503.10150]; StructRAG 53.00 [2410.08815].

## Disagreement, document level against content level

| graph | OUTPERFORMS edges | pairs claimed both ways | across two papers |
| --- | --- | --- | --- |
| document level, 200 papers | 1,059 | 7 | 0 |
| content level, 60 papers | 174 | 3 | 1 |

The one that spans two papers is GraphRAG against plain RAG. 2506.05690 reports GraphRAG at
50.93 complex reasoning accuracy against 41.35; 2502.11371 reports RAG better on single hop
questions and on detail. The metric is what reconciles them, and that reconciliation is the
answer a reader wants.

| method | W | L |
| --- | --- | --- |
| GraphRAG | 3 | 11 |
| Self-Rag | 9 | 1 |
| LightRAG | 6 | 4 |
| IRCoT | 5 | 3 |
| G-Retriever | 2 | 3 |

## A second field, same code, no tuning

`foundation models for tabular data`, 60 papers, 1,705 triples in 864s.

| | graph RAG | tabular foundation models |
| --- | --- | --- |
| node labels | Paper, Method, Task, Benchmark, Component, Challenge | Paper, Model, Task, Benchmark, Technique, Limitation |
| busiest relation | UTILIZES 581 | APPLIES 435 |
| comparison edges | OUTPERFORMS 174 | OUTPERFORMS 227 |
| triples | 1,847 | 1,705 |

| question | rows | verdict |
| --- | --- | --- |
| Which models outperform TabPFN, and on what benchmark? | 25 | correct and current |
| What limitations do tabular foundation models claim to address? | 3 | searched for a Model literally named "tabular foundation model" instead of aggregating |
| Which techniques are applied by models evaluated on OpenML? | 25 | correct |
| What is the most evaluated benchmark and which models use it? | 15 | correct |

Unedited: TabICLv2 outperforms RealTabPFN-2.5 and TabPFN-2.5 on TALENT and TabArena
[2602.11139]; TabPFN-2.5 outperforms TabPFNv2 on TabArena-Lite and TabArena [2511.08667];
nanoTabPFN outperforms TabPFN on TabArena.

The pool for each field lands on the right papers with no tuning: TabICL, TabPFN-2.5, TabICLv2
and TabDPT for tabular; LLaDA, Dream 7B, Block Diffusion and MDLM for diffusion language models;
DistServe, Sarathi, Splitwise and vLLM for serving.

## Session two, what worked and what did not

| idea | verdict |
| --- | --- |
| extra queries as candidate expansion | works, Pareto, +24% at rank 50 |
| extra queries fused by RRF | loses at every budget |
| content level triples against a proposed schema | works, and fixes the merge problem |
| the model proposing the schema per field | works, adapts, but under specifies comparison until told |
| the model writing cypher against that schema | 7 of 9 questions over two fields |
| ephemeral neo4j from the store | works, 1 second to load, no recompile |
| LeyLine as the full text sampler | no measurable job, rank order is already the right sample |
| covering the pool on purpose when sampling | worst of the four by a wide margin |
| cross paper disagreement | 1 pair at content level, 0 at document level |

# The joined graph

The citation half and the content half sharing one set of Paper nodes, so a content node reaches
a date through the paper that stated it.

| | |
| --- | --- |
| load | 0.9s |
| nodes | Paper 1011, Model 306, Limitation 218, Technique 190, Task 116, Benchmark 85 |
| edges | CITES 28,221, STATES 1,406, APPLIES 435, SOLVES 357, ADDRESSES 282, PROPOSES 252, OUTPERFORMS 227, PERFORMS_ON 152 |

## Does the schema let you reach the newest work

Question: the strongest tabular foundation models, and which is most recent.
Ground truth in the corpus: TabPFN-3 (2605.13986, 2026-05), TabICLv2 (2602.11139, 2026-02),
TabPFN-2.5 (2511.08667, 2025-11). All four are inside the 60 papers the graph was built from,
at pool ranks 12, 2, 1 and 0.

| | versions named |
| --- | --- |
| Gemma 26B with no graph | none. TabPFN, GReaT, TabLLM, plus "TabPFN's updated iterations" |
| cypher over the schema | TabPFN-2.5, TabPFN-3, TabICLv2 |

Before the join, the same question returned "the rows do not contain enough information to
determine which model is the most recent", because the content load carried no dates. After it,
`(p:Paper)-[:STATES]->(m:Model)` dates every model: TabPFN-3 2026-05-13, TabICLv2 2026-02-11.

## Citation grounding on the cypher path

The answering step invented `2402.07630`, a graph RAG paper absent from the tabular graph, while
the correct sources 2511.08667 and 2501.02945 sat in the rows it was given. Striking any id the
rows did not carry now rewrites it to `[unsupported]`, the same guard the claim path already had.

## Five questions against the joined graph

| question | rows | verdict |
| --- | --- | --- |
| Which models appeared in 2026 and what techniques do they apply? | 25 | correct, used `p.year` through STATES |
| Which limitation is named by the newest papers but not before 2025? | 25 | correct temporal set difference |
| Which model is most recent and what does it outperform? | 1 | wrote `ORDER BY m.date` on a Model, which has no date |
| What do papers citing TabPFN with critiques or compares intent say? | 0 | wrote `(Paper)-[:CITES]->(Model)`, but CITES joins Paper to Paper |
| Most cited paper, what do its citers propose? | 0 | coverage, see below |

Two of the three failures are the same missed inference: to get from a content node to the
citation layer you must go `(Model)<-[:STATES]-(Paper)-[:CITES]->`, and the model does not make
that hop unless shown it.

## What limits the join

| measure | value |
| --- | --- |
| papers in the graph | 1,011 |
| papers with content | 58 (5.7%) |
| CITES edges with content on one end | 8,400 (29.8%) |
| CITES edges with content on both ends | 1,602 (5.68%) |

A cross graph question walks a citation edge and needs content on the far side, and that holds
for one edge in eighteen. The join is only as useful as the content coverage, and reading 60 of
1,000 papers is what caps it.

## Files

| file | does |
| --- | --- |
| `pool.py` | the retrieval, cached per question |
| `extract.py` | typed entities from abstracts |
| `canon.py`, `merge.py` | the two merge rules that were compared |
| `graph.py` | assembles pool and extraction into the typed graph |
| `gaps.py`, `gaps2.py` | the gap detectors and the generic node correction |
| `claims.py` | grounded claims from results sections |
| `why.py` | grounded rationale from method sections |
| `relate.py` | claims to typed relations |
| `tourney.py` | the tournament reading and the self report correction |
| `qa.py`, `ask.py` | one question to an answer with spans |
| `traverse.py` | the model writes a query over the relation graph |
| `schema.py` | the model proposes the node and relation types for this question |
| `content.py` | content level triples against that schema, quote checked |
| `neo.py`, `neo2.py` | ephemeral neo4j, document level and content level loads |
| `cyq.py` | model written cypher over the document level graph |
| `sample.py`, `bysample.py` | the four samplers and their comparison |
| `expand2.py` | extra queries as candidate expansion rather than rank fusion |
| `topic.py` | one field end to end |
| `neo3.py` | the citation and content halves in one graph |
| `ask3.py` | questions that need both halves |
| `reject.py`, `gapfind.py`, `induce.py` | the three schema refinement signals, all negative |
| `versiontest.py` | unaided against cypher on reaching the newest version |
| `missed.py` | what the pool ranks that no survey cited |
| `expand.py` | model written extra queries against the survey key |
