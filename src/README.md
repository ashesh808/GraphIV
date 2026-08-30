# src

The importable library, empty while the serve path is rebuilt against the three-table store.

```
retrieve/    query -> a graded, ranked cohort        not yet written
generate/    cohort -> a grounded, cited review      not yet written
serve/       MCP tools and the dashboard             not yet written
core/        config, store, embedding, LLM           not yet written
```

The pre-rewrite versions are parked in `.legacy/graphiv/`, which git does not track. Nothing
here is an entrypoint, and nothing here imports `scripts/`.

Preprocessing has no code here. `scripts/citation_labeler/` carries the two modules it imports
as siblings, the same way `citation_preprocess/` carries `matcher.py`.
