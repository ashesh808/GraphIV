# tests

Empty while `src/` is rebuilt.

The pre-rewrite suite covered retrieval, the mode decision in front of it and full-text
acquisition against a hand-built pool, with no database, no embedding endpoint and no GPU. It is
parked in `.legacy/tests/` and comes back a file at a time as each module is repointed at the
three-table store.

Run: `uv run pytest tests -q`.
