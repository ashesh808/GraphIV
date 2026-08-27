# tests

Unit tests for the retrieval stage, the mode decision in front of it, and full-text acquisition.
Every case builds its pool by hand in `conftest.py` and stubs the model call, so the suite
needs no database, no embedding endpoint and no GPU, and finishes in under a second.

```
tests/
├── conftest.py       six papers over four citation edges, plus a query and a frontier spec
├── test_select.py    score functions, the shared assembler, fusion and the two flags
├── test_readers.py   null, constant and gold readers; llm is checked only via the registry
├── test_build.py     assembling a pipeline from stage names, and what an unknown name does
├── test_refine.py    candidate normalization, the mode classifier and the rank flag it sets
└── test_fetch.py     local-first acquisition, against a redirected store and no network
```

Run: `uv run pytest tests -q`.

Behaviour against the real store is not covered here.
The selector registry is checked against the pre-refactor rankers on all 60 frozen survey pools
by `experiments/_harness/bench/parity.py`, which needs the frozen pools and is not part of
this suite.
