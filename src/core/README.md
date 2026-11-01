# core

The data types every layer passes around, and the clients underneath them.
It imports no other GraphIV layer, so it sits at the bottom of the layer order.

```
schema.py              the shapes that cross a step boundary, and the Retriever and Reranker protocols
parse_graph_export.py  the citation graph export, read into flat arrays a query can slice
embed.py               the query vector, from the same endpoint the corpus was embedded with
llm.py                 the local router, with every reply cached by the hash of its prompt
fetch.py               where a paper's full text sits on disk, fetched from arXiv when it is missing
config.py              TOML configuration, with each relative path anchored to the file's own directory
paths.py               checkout or bundled resource locations and default configuration files
```

`Paper` and `Query` are the only shapes that cross a step boundary.
A `Paper` field left at `None` has not been computed yet, and the first step that needs it fills it in.
