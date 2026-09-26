# eval

Benchmarks that score a retriever+reranker pipeline against an answer key. Everything here is
importable and none of it is an entrypoint, so a run is driven from `scripts/` or a notebook.

```
survey_match.py    SurveyMatch, scored against a survey's own reference list
```

One case is one arXiv survey. The query is its title with the survey boilerplate stripped, the
answer key is the references it resolved to, and the match is the share of them that came back.

```python
from src.eval.survey_match import SurveyMatch

bench = SurveyMatch(PG_DEST, cache_path=Path("data/eval/survey_match.json"))
print(bench.run(lambda s: [p.arxiv_id for p in query.do_query(s.query, 4000, 400)], k=400))
```

`Survey.date` is the cutoff and it is passed to the pipeline rather than applied afterward. A
pipeline that ignores it is not corrected, it just spends slots on papers that cannot be hits.
