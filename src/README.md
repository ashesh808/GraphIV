# src

The importable library, being rebuilt against the three-table store.

```
core/        config, contracts, embedding, LLM              schema.py only
eval/        benchmarks that score a retriever pipeline      survey_match.py
retrieve/    query -> a graded, ranked cohort               not yet written
generate/    cohort -> a grounded, cited review             not yet written
serve/       MCP tools and the dashboard                    not yet written
```

The pre-rewrite versions are parked in `.legacy/graphiv/`, which git does not track. Nothing
here is an entrypoint, and nothing here imports `scripts/`.

Preprocessing has no code here. `scripts/citation_labeler/` carries the two modules it imports
as siblings, the same way `citation_preprocess/` carries `matcher.py`.
