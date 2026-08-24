# retrieve

Knowledge graph to a graded, ranked cohort of papers. Nothing here calls a writer model, so a cohort is reproducible from the query vector alone.

## Modules

```
subgraph.py      topical pool, induced citation subgraph, eras, main path, tensions
hybrid.py        vector and lexical pool fusion, then the category anchor
refined.py       topic-anchored pool plus the year-filtered frontier pull
topic_anchor.py  topic-tree leaf anchoring
grade.py         the reader pass, cached per question and paper
pagerank.py      personalized PageRank over the induced subgraph
trajectory.py    magnet-pulled lineage selection, shipped as a quota over PPR
frontier.py      frontier-aware landmark ranking
landmarks.py     set-coverage objectives, kept for research and not shipped
recency.py       per-topic frontier detection and age-normalized scoring
```

`landmarks.py` is the one module the shipped path never calls. It holds PPR's competitors
from experiment 02-06, which PPR beat on gold recall.
