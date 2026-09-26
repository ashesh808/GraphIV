# core

The contracts every other subpackage reads, and the plumbing under them. Nothing here imports
from `retrieve`, `generate`, `serve` or `eval`, so it sits at the bottom of the layer order.

```
schema.py             Paper and Query, plus the Retriever and Reranker protocols
parse_graph_export.py the citation graph as CSR, loaded by mmap
llm.py                the local router, every completion cached by the hash of its prompt
```

`Paper` and `Query` are the only shapes that cross a step boundary. A `Paper` field left at
`None` has not been computed yet, and filling it is the job of the first step that reads it.
