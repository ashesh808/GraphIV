# graphiv

The importable library: everything the pipeline and the endpoint are made of, and nothing that runs on its own.

## Subpackages

Arrows point down only, which `import-linter` enforces as a layers contract in `pyproject.toml`.

```
serve/       MCP tools, the Research Library dashboard
generate/    graded cohort -> a grounded, cited literature review
retrieve/    knowledge graph -> a graded, ranked cohort
preprocess/  metadata and files -> labels and a citation graph
download/    metadata -> files on disk
core/        config, store, embedding, LLM, the shared data contracts
```

Each subpackage carries its own README. Configuration arrives from `config.toml` through
`core.config`, so no module hardcodes a path.

## Running it

Nothing here is an entrypoint. The runnable stages live in `scripts/`.
