# retrieve

A question into a ranked cohort of papers, with no language model anywhere on the path. One retriever picks a pool by cosine, two expanders append what the best matches cite and what cites them, and one scorer ranks the whole pool by its position in the citation graph.

```
cosine.py   CosineRetriever, the seed
expand.py   AncestorExpander and FrontierExpander, which only append
scorer.py   Weights, the transforms and GraphScorer, the only step that ranks
query.py    PaperQuery, which owns the order and nothing else
```

```python
pipeline = PaperQuery(
    retriever=CosineRetriever(PG_DEST),
    rerankers=[AncestorExpander(graph, PG_DEST),
               FrontierExpander(graph, PG_DEST),
               GraphScorer(graph, Weights())],
    limits=[20_000, 20_000, 1000],
)
papers = pipeline.do_query(text, emb, retrieve_limit=5000, return_limit=1000, max_date=cutoff)
```

## Why the steps split where they do

An expander appends and ranks nothing, so the two commute and neither can delete what the other found. That also separates the two questions a result has to answer: turning off an expander changes which papers were reachable at all, and turning off a channel changes how the reachable ones were ordered.

The scorer is the only step that cuts, and it does it once, because the channels are read together rather than as a chain. Ancestors lead when the answer is a field's own history and co-citation leads when it is what came next, and in a chain whichever ran first would decide what the second was allowed to see.

`GraphScorer` opens no connection. Every step above it fills `title`, `abstract`, `date` and `cosine`, which costs nothing extra because those columns sit on the same heap page as the id, so the scorer reads only the export and numpy.

## The channels

All six are walks from the same core, the top papers of the pool by cosine, over the citation graph induced on the pool.

```
anc     what the core cites
fro     what cites the core
cocite  papers the core's citers also cite
couple  papers that cite what the core cites
anc2    what the core's ancestors cite, one step further back
fro2    what cites the papers that cite the core, one step further forward
anc_decay  decay ** distance walking backward from the core, zero past the depth
fro_decay  decay ** distance walking forward from the core, zero past the depth
```

`anc` and `fro` are exactly zero for any paper the core does not touch directly, which is every paper more than one hop out. The two decay terms are what let those score at all, since a one-step channel cannot separate a paper two hops out from one the walk never reaches.

Every channel comes back on `[0, 1]`, so each factor of the score sits on `[1, 2 ** exponent]` and a channel a paper scores nothing on is neutral rather than fatal. The walk channels pass through `compress_long_tail` and the distance channel does not, since a decay curve already spans the range and compressing it would rescale it onto its own maximum.

## Weights

An exponent of zero makes its factor exactly one and drops the term, so an ablation is `replace(weights, couple=0.0)` with no pool rebuild. The exponents are not universal: the hub denominator, recency and `anc2` all change sign between a question about a field's history and one about its frontier, so they belong to a named setting rather than to the code.
