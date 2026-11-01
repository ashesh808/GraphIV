# From one question to one document

How the whole thing is put together, in the order it runs.
The running example is the litsearch question, and every number here came off a real run on disk.

The question:

> I am building a system that finds the papers a literature review should cite, over a few million
> arXiv papers. I know dense retrieval with a scientific embedding model, and I know the LLM
> reranking line of work. I am trying to decide whether the citation graph is a useful signal at
> query time or whether everyone has settled on baking it into the embedding at training time.
> What is the current state, and where are the open problems?

What it costs, cold, at each rung of the dial: 59.6s, 325.4s, 602.6s.

---

## 1. Refine, the model names the area

In: the question as typed.
Out: `Refined`, holding the area, the method words, the sub-queries, what to exclude, and the mode.

One call to Gemma, cached by the sha1 of the question, so asking twice costs nothing.

```
area     Integrating Graph Topology into Dense Retrieval for Scientific Document Discovery
methods  Graph Neural Networks, Bi-Encoder Architectures, Cross-Encoder Reranking,
         Knowledge Graph Embeddings, Link Prediction, Contrastive Learning
mode     survey
```

The anchor is those two glued together, `"{area}. {methods}"`, and it is the only thing the area
vector is ever made from.

Why this exists at all: the question is written in researcher-speak and the corpus is embedded in
paper-speak.
Nobody writes an abstract that says "I am trying to decide whether".
The anchor is a manufactured document, shaped like the papers it is meant to find.

## 2. Retrieve, twice

In: the question and the anchor, each embedded.
Out: two pools.

Each call runs the `survey` recipe, which is a retriever and two expanders and nothing else:

| step | recipe | what it adds |
| --- | --- | --- |
| CosineRetriever | `LIMIT 5000` | the top 5,000 of the corpus by cosine, under the date cap |
| AncestorExpander | `TOP_K 200` | what the core of the pool cites |
| FrontierExpander | `TOP_K 200` | what cites the core |

The scorer named in the recipe does not run here.
`build_pool` stops after the expanders, because the score has to be gated and the gate is not
retrieval's business.

## 3. The pool

In: two pools.
Out: one pool, papers deduplicated by arXiv id, each keeping the higher of its two cosines.

Measured sizes on real runs: 6,453 on a narrow question, 13,158 on RAG, 15,132 on this one,
15,745 on tabular.
The two 20,000 hop caps in the recipe never bind, and the union is far under twice one pool because
both probes point at the same field.

## 4. The area cosine

In: the pool ids and the area vector.
Out: one float per paper, in one round trip.

```sql
SELECT arxiv_id, 1 - (embed_full <=> area_vector) FROM papers WHERE arxiv_id = ANY(pool)
```

Every paper now carries two cosines, and they answer different questions.
Cosine to the question asks whether the paper matches what was typed.
Cosine to the area asks whether the paper belongs to the field being asked about.

## 5. Score, then gate

In: the pool, the citation graph, the exponents, the area cosines.
Out: the ranking.

The graph score is the six bounded channels over the citation graph, the ones already tuned on
SurveyMatch, and then every score is multiplied by the gate:

```
score *= (area cosine / the pool's best area cosine) ** 4
```

The exponent 4 was measured best on both question sets.
It is deliberately brutal: a paper at 80 percent of the best area cosine keeps 0.41 of its score,
one at 50 percent keeps 0.06.
The citation graph loves famous papers, and this is the thing that stops a famous off-topic paper
winning on structure alone.
On hard, broadly worded questions it took on-topic from 0.600 to 0.743.

## 6. Two cuts off one ranking

These are different depths with different filters, and confusing them is the easiest mistake here.

One ranking comes out of the score, and two slices are taken off it for two different jobs.
**The head** is the top 300 whatever their dates, and it exists so the mining has old papers to draw a line through.
**The window** is any rank at all as long as the paper is from the last 365 days, and it exists so the reader only grades what the area is doing now.

| cut | how deep | filter | what it feeds |
| --- | --- | --- | --- |
| the head | 300, or 400 at level 2 | none | the edges, the magnets, the lines |
| the window | the whole ranking | published in the last 365 days | the reader, then the state |

## 7. The reader

In: the top 100 of the window, 150 at level 1, 250 at level 2.
Out: a role and a relevance for each, and the unrelated ones dropped.

Six roles: `foundational`, `core`, `frontier`, `adjacent`, `survey`, `unrelated`.

What survives, cut to 20 papers at level 0 and 30 at level 2, is **the state**, printed in the
document as "What this area currently is".

The reader is never told today's date, which is why the method table carries its own date floor
rather than trusting a `frontier` grade.

## 8. The edges

In: the head.
Out: every labeled citation with both ends inside it, carrying the intent and the sentence.

This is the induced subgraph.
Not papers about the area, but papers about the area talking to each other.

## 9. The magnets

A magnet is a paper the field takes a position on.

```
stance(p)  = sum over in-pool citers c of W[intent(c -> p)] * cos(c)
total(p)   = sum over in-pool citers c of cos(c)
magnet(p)  = stance(p) * stance(p)/total(p) * cos(p, named area)
```

| intent | W | edges in the corpus |
| --- | --- | --- |
| extends | 1.0 | 2.5M |
| critiques | 1.0 | 2.7M |
| compares | 0.8 | 5.2M |
| uses | 0.4 | 11.6M |
| motivates | 0.15 | 0.66M |
| background | 0.0 | 51.1M |

Each of the three factors removes one failure of the old definition, which was whatever the reader
graded 2:

| factor | what it removes |
| --- | --- |
| stance mass | a paper nobody argues with, however often it is named |
| stance share | a paper cited as background by everything, the generic hub |
| area cosine | a paper argued about for a reason other than this question |

On this question the head of 300 produced 216 magnets, topped by Dense Passage Retrieval at 1.000
with stance share 0.37, argued by compares 26, critiques 11, extends 10.

## 10. The lines

In: the edges and the magnets.
Out: the lines, printed as "How it got here".

The graph is flipped to point cited to citing, so walking it runs forward in time.
Reach is how much magnet mass sits ahead of a paper, halved at every hop, and the walk starts at
the highest-reach paper and steps forward toward whatever has the most reach left.

Then the magnets just collected are knocked down to 0.4 of their weight and it walks again.
Fifty lines per run, ten runs with different seeds.
A line found under many seeds is a real lineage, one found once is the sampler wandering, and that
count is kept.
Lines contained in longer lines are dropped, and what is left is ranked by the magnet mass on it
times how often it was rediscovered.

Level 0 keeps 4 lines, level 1 keeps 5, level 2 keeps 6.

## 11. The disputes

In: the edges.
Out: one `critiques` edge per pair, strongest target first, with the sentence.

Read off the edges directly and never off the lines.
One critique sits on several lines at once, so reading them off the lines returns the same quote
four times, which is exactly what happened before this was separated out.

## 12. The successors

In: the top of the state.
Out: papers from the last 240 days that `extends`, `critiques` or `compares` against it, at intent
confidence 0.60 or better.

Printed as "What has just appeared against it".

This exists because a three month old paper scores exactly zero on every channel in step 5.
Nothing has cited it yet.
But it cites, and the intent on that edge exists the day it appears.
This is the only way the cold start case is reachable at all.

## 13. Full text

In: 8 papers at level 0, 16 at level 1, 24 at level 2, magnets first then the state.
Out: the limitation sections off the HTML already on disk, read by the model.

Printed as "What is still open, in the authors' own words".

## 14. The schema, filled

Off at level 0. 120 papers at level 1, 300 at level 2.

The model reads six titles and abstracts, decides what is worth knowing about every paper for this
particular question, and that becomes the fields.
Then every paper's full text is read into those fields.

Printed as "The papers side by side".

## 15. What other papers measured

Off at level 0. 40 magnets at level 1, 100 at level 2.

For each magnet, find the papers that cite it, ordered by how close the citer sits to the named
area, and pull what their results tables say about it.
24 citers at level 0 and 1, 40 at level 2.

The point is independence.
A paper quoting its own abstract is the paper's own claim.
A number reported about X by a paper that benchmarks against X is a second source, and the
`compares` edges say exactly where those live.

Ordering the citers by area cosine is not cosmetic.
Ordering them by date put BERT on FUNSD, drone constraints and geographic distance into a table
about retrieval, because a famous backbone is benchmarked against everywhere.

## 16. The method table

Rows are methods, not papers.
Columns are decided per question by the model.
20 rows at level 0, 40 at level 1, 60 at level 2, drawn only from what the reader called `frontier`
or `core`, and only from the last 4 years.

**Design.** The model is shown eight titles and abstracts and returns the columns.
At least two must be a **closed column**, meaning an axis carrying a short list of options the
answers snap onto.
One closed column must be the axis the question itself turns on.
The options have to cover every paper between them, so one of them is the plain answer a method
doing nothing special would give.
Exactly one column is a value column, which is the headline number and the benchmark it was on.

**Extract.** Each paper's abstract, method section, results section and up to three numeric tables
go in, and out comes the method the paper is titled after.
An answer on a closed column has to be one of its options, or two words of the model's own naming,
and never the literal word "other".

**Merge.** Rows with the same normalized method name become one row carrying both papers.

**Repair.** Any closed column whose options missed more than 40 percent of the rows gets widened
and re-snapped.

Printed as "The methods side by side".

## 17. The spread and the cross product

Count each closed column down its own length, and cross-tabulate two of them against each other.

```
query time 25 / none 5 / pre-trained 3
in-context learning 29 / gradient boosting 1
sparse features 34 / concept vectors 13
```

Printed as "What people are actually doing".

## 18. The gaps

The empty cells of two closed axes crossed against each other.

A cross-tab always has empty cells and most of them are combinations that cannot hold at once, so
the mechanical table is only evidence.
A second model call issues the verdict on each empty cell: unexplored, impossible, or done
elsewhere.

Printed as "Where the gaps are".

## 19. The composer

In: the lines, the disputes with their sentences, the counted table, the gaps, the successors, and
the stated limitations.
Out: four sections of prose.

```
The short answer
How the field got here
Where people disagree
What is missing
```

Two rules make it trustworthy.
A claim about a particular paper ends with that paper's arXiv id in brackets.
A claim read off the counted table or off the cross product carries no id at all, because those
blocks name no paper, so a count never gets an id attached to it.

Then every id in the written text is set-differenced against the evidence it was given.
Across four runs, 49 of 49 ids were grounded.

## 20. The document

Sections in order:

```
# the named area
the composed prose
The methods side by side
What people are actually doing
Where the gaps are
What this area currently is
How it got here
What has just appeared against it
The papers side by side
What other papers measured about these
What is still open, in the authors' own words
The working
```

"The working" is the timings table, one row per stage, so any line of the document can be traced
back to the stage that produced it.

---

## The dial

| | level 0 | level 1 | level 2 |
| --- | --- | --- | --- |
| name | the story | read the papers | read everything |
| cold, on a never-asked question | 59.6s | 325.4s | 602.6s |
| the state | 20 | 25 | 30 |
| the head | 300 | 300 | 400 |
| the reader reads | 100 | 150 | 250 |
| lines kept | 4 | 5 | 6 |
| full text | 8 | 16 | 24 |
| schema filled | off | 120 | 300 |
| measured | off | 40 magnets | 100 magnets |
| table rows | 20 | 40 | 60 |
| methods found | 20 | 36 | 61 |
| of which the table stage | 26.9s | 54.8s | 82.7s |
| of which the composer | 3.1s | 3.8s | 3.6s |

Every level produces the same document with the same sections.
The dial buys reading, not structure.

---

## Where each step lands

| step | module | package | model? |
| --- | --- | --- | --- |
| 1 refine | `refine.py` | answer | yes |
| 2 retrieve | `cosine.py`, `expand.py`, `query.py` | retrieve | no |
| 3 the pool | the caller | answer | no |
| 4 area cosine | `anchor.py` | leyline | no |
| 5 score and gate | `rank.py`, `scorer.py` | leyline, retrieve | no |
| 6 the two cuts | the caller | answer | no |
| 7 the reader | `roles.py` | answer | yes |
| 8 the edges | `store.py` | leyline | no |
| 9 the magnets | `magnet.py` | leyline | no |
| 10 the lines | `magnet.py` | leyline | no |
| 11 the disputes | `magnet.py` | leyline | no |
| 12 the successors | `successor.py` | leyline | no |
| 13 full text | `fulltext.py` | answer | yes |
| 14 the schema | `schema.py` | answer | yes |
| 15 measured | `measured.py` | answer | yes |
| 16 the method table | `methods.py` | answer | yes |
| 17 spread | `methods.py` | answer | no |
| 18 the gaps | `methods.py` | answer | yes |
| 19 the composer | `compose.py` | answer | yes |
| 20 the document | `write.py` | answer | no |

Everything in the leyline column is graph and vectors.
No model is ever called there, nothing is read off disk there, and nothing there knows what a
markdown heading is.
That is what makes it the part that can be measured on its own, and the part that can be served as
its own tool in two seconds instead of ten minutes.
