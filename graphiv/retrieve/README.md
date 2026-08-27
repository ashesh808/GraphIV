# retrieve

Knowledge graph to a graded, ranked cohort of papers.
Retrieval is three swappable stages behind one contract, so a flat baseline and the production
path are the same type and run through the same loop.

## The contract

```python
retriever = build(pool="graph", reader="llm", selector="joint")
got = retriever.retrieve(Query(text=..., budget=80, now=datetime.now()))
got.papers   # the ranked cohort
got.pool     # what was considered, plus edges, grades and a per-stage trace
```

`Query.max_yymm` and `Query.exclude` freeze the corpus, which is what lets an eval run see only
the world a survey saw.

## Modules

```
api.py           Query, Pool, Selection, Retrieved, and the four stage protocols
build.py         build() from stage names, PRESETS for the older single rank flag
pools.py         graph, vector and lexical pool builders
readers.py       null, constant, gold and llm readers
select.py        score functions, the shared assembler, the selector registry
subgraph.py      topical pool, induced citation subgraph, eras, main path, tensions
hybrid.py        vector and lexical channel fusion by reciprocal rank
refined.py       topic-anchored pool plus the year-filtered frontier pull
topic_anchor.py  topic-tree leaf anchoring
grade.py         the reader pass, cached per question and paper
pagerank.py      personalized PageRank over the induced subgraph
trajectory.py    the magnet-pulled consensus walk, shipped as a quota
frontier.py      the pre-registry frontier ranker, kept as the parity reference
joint.py         the pre-registry joint ranker, kept as the parity reference
landmarks.py     set-coverage objectives, kept for research and never shipped
recency.py       per-topic frontier detection and age-normalized scoring
```

## Registries

| stage | keys |
| --- | --- |
| pool | `graph` `vector` `lexical` |
| reader | `null` `constant` `llm` |
| selector | `joint` `frontier` `ppr` `trajectory` `indegree` `topk` |

A selector is a score function plus three flags, since every shipped ranker turned out to be the
same reserve-fill-quota shape with a different score.
`GoldReader` grades from an answer key and is evaluation only.

`landmarks.py` is the one module the shipped path never calls.
It holds the set-coverage objectives from experiment 02-05, which fusion beat by 140 papers.
