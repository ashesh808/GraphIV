# deep-research

The un-numbered flagship: the full deployed pipeline, dogfooded and compared head to head against hosted deep-research tools.

## Layout

```
run.py       thin entry into code/deep_research.py
code/        the driver plus h2h_verify.py, the citation verifier
results/     h2h/ and dogfood/ report sets, with the verification output
report/      the write-up
cache/       per-run cache
```

`code/h2h_verify.py` works on any report, including one written by a hosted tool, and falls
back to live arXiv when an id is missing from the local corpus.

## Running it

```sh
uv run python experiments/deep-research/run.py
```
