Rewrite specs for src/retrieve

```
core/
    schema.py
query/
    retrievers/
        cosine.py
    rerankers/
        _grade.py
        graph.py
        llm_grader.py
    __init__.py
    query.py
```

# Pipeline

query.py contains PaperQuery as the main class, it expects the following

`def __init__(self, retriever: Retriever, rerankers: List[Reranker], limits: List[int | None])`
sets retriever, rerankers and limits, one limit per reranker in the same order
`def do_query(self, text: str, retrieve_limit: int, return_limit: int) -> List[Paper]`
builds the `Query` once so no step downstream re-embeds, then

```python
query = Query(text=text, emb=embed(text))
papers: List[Paper] = self.retriever.retrieve(query, retrieve_limit)
for reranker, limit in zip(self.rerankers, self.limits):
    papers = reranker.rerank(query, papers, limit)
return papers[:return_limit]
```

Three invariants hold at every step.

- `limit` is the most papers a call may return, `None` for no limit
- a step cuts by its own key, never by cosine, since a step that ranks on something else would
  otherwise delete what it just added
- the pool is unique by `arxiv_id`, so a step that appends dedupes against what is already there

# Schema

core/schema.py

A field left at `None` has not been computed yet, which is what the fill rules below test.

```python
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    date: date # pulled from db, always exist
    cosine: float | None = None
    citations: int # pulled from db, always exist
    ancestors: float | None = None
    frontier: float | None = None
    cocite: float | None = None
    llm_score: int | None = None
```

```python
class Query:
    text: str
    emb: List[float]
    max_date: date | None = None
```

`max_date` caps what a query may see, so an eval case retrieves the world its survey retrieved.
It rides on `Query` rather than on `PaperQuery`, since every step that touches the database
needs it and only `Query` reaches all of them.

Retriever:
`def __init__(self, PG_DEST)`
`def retrieve(self, query: Query, limit: int) -> List[Paper]`
Reranker:
`def __init__(self, **kwargs)`
`def rerank(self, query: Query, papers: List[Paper], limit: int | None) -> List[Paper]`

# Shared

Every step that reads a field it did not compute fills that field first.
Each fill is one function, not a reimplementation per file.

| fill | does |
| --- | --- |
| `_load(ids, PG_DEST) -> List[Paper]` | builds a Paper from an id, since title, date and citations are not optional |
| `_fill_cosine(query, papers, PG_DEST)` | cosine, in a single query against the embedding index |
| `_fill_llm_score(query, papers)` | llm_score, through `_score_batch` |

query/rerankers/_grade.py

`_score(query, paper) -> int` is the cache unit, keyed `(sha1(query.text)[:12], arxiv_id)` in
sqlite, and `_score_batch` is the concurrency wrapper that only calls it on the misses.

# Retrievers

cosine.py

- highest `limit` papers by cosine over the whole table, `date <= query.max_date` when it is set
- fills `papers[i].cosine` on the way out, since it is the one step that has it for free

bm25, the lexical channel and their RRF fusion were measured and cut at +0.0033, p=0.307.
The topic-tree filter was measured and cut: it keeps 34% of the pool and 50-60% of the key.

# Rerankers

graph.py class `GraphReranker`

kwargs `PG_DEST`, `top_k`, `hop_limit`, `alpha`, `min_citers`.

Loads one subgraph and reads every graph field off it, so nothing walks the citations table twice.

| step | rule |
| --- | --- |
| weights | `w[i]` is the cosine of the top `top_k` incoming papers and 0 elsewhere, divided by its sum |
| expand | one citation hop each way, `hop_limit` per side, ranked by distinct partner count and gated at `min_citers` |
| adjacency | `A[i][j] = 1` when paper j cites paper i, so one multiply is a hop backward in time |
| ancestors | `A @ w`, the pool weight that cites a candidate |
| frontier | `A.T @ w`, the pool weight a candidate cites |
| cocite | `A @ f`, where `f` marks the top 500 by `frontier * recency * cosine` |
| cut | top `limit` by `cos^0.5 * rec * lg(ancestors)^2 * lg(cocite)^2 / (1 + citations)^alpha` |

`rec` is `1 / (1 + age_years)`, `nz(x)` is `x / max(x)` and `lg(x)` is `nz(log1p(100 * nz(x)))`.
The 100 is what makes the log compress, since `nz` leaves the values where `log1p` is linear.
Every exponent is a weight in a log-linear score, so the two graph terms outvote cosine 4 to 1.
`alpha` is the only dial between the two halves of the question, 0.3 for what got them here and
0.7 for what people are doing now.

llm_grader.py class `LLMGraderReranker`

- fills `llm_score` in -2..2, drops the `-2` outright as a rejection
- cuts to `limit` by `cosine * (llm_score + 2) / 4`, not by `llm_score`, which is five buckets
  and cuts the boundary one by list order

It loses as a reranker, 0.647 for the graph alone against 0.603 fused, so it ships off the
retrieval path and stays for grading a cohort that is already chosen.

LeyLine left retrieval on 2026-09-02 and belongs to report generation.
