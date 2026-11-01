# tests

Tests for reusable source components, application routes, and offline helpers. Fixtures use small graphs, temporary files, fake stages, and local HTTP servers, so the default suite needs no external database, model, or network service.

```
run.py                runs the whole suite, or one subdirectory
core/                 configuration and corpus file access
retrieve/conftest.py   an eight paper citation graph written in the format stage2 exports
retrieve/             the graph reader, the score, the expanders and the pipeline
miner/                eras, lineages, and successor ordering
report/               citation grounding
mcp/                  MCP argument handling, area selection, and past runs
apps/                 runtime HTTP routes and application boundaries
offline/manager/      job execution, scheduling, snapshots, benchmarks, and publishing
export/               dataset publication helpers
recipe_tuning/        recipe fitting
```

```sh
uv run python tests/run.py
uv run python tests/run.py retrieve -v
uv run pytest tests/mcp tests/apps tests/offline -q
```

## The fixture graph

`retrieve/conftest.py` builds eight papers and eight edges, chosen so that every quantity the retrieval code computes has one obviously correct answer.

```
p0 -> p4, p5      p1 -> p4      p2 -> p5, p6      p3 -> p0, p1      p7 -> p3
```

p0 and p1 carry the two highest cosines, so they are the core. p4 and p5 are what the core cites, which makes them the ancestors, and p4 leads because both core papers reach it. p3 is what cites the core, which makes it the frontier. p7 sits two hops out and scores zero on every one-step channel, which is what the distance channel exists to fix. p3 is dated after p0 and p1, so a date cap of 2021 removes it and the citation counts of p0 and p1 fall to zero.

`-m "not slow and not gpu"` is the default, so a heavy test added later is skipped unless `--slow` is passed.
