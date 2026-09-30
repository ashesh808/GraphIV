# graphiv_manager

One page that keeps the store current: the arXiv snapshot Kaggle publishes each week is fetched and staged, checked against the store, then run through every stage, and the dashboard shows what each table holds.
Jobs run one at a time in the order they were queued, each step in its own process group, and a step that exits nonzero halts the job so the next stage never reads a queue that did not fill.
`citation_labeler/` is left out, since training a labeler is a one-time job run by hand.

```
main.py       the entrypoint, which stops a running job with SIGINT before it exits
schedule.py   the loop that picks the next job, the snapshot check, and every number the page reads
jobs.py       a job as ordered steps, the runner, and the SIGINT, SIGTERM, SIGKILL escalation
stages.py     every stage as a recipe: its script, what it reads, writes and fetches, and the dry run
stats.py      one query per dashboard chart, each result kept as json in the state directory
discover.py   every runnable script, its flags off --help, and what it needs off its source
probes.py     the store, both endpoints, the router, the GPU, the disks, and the queue counts
snapshot.py   the snapshot in use, the resumable fetch that stages arxiv-new.json, and the commit
routes.py     the json routes and the page
webui/        the page, in the same four palettes as the dashboard
```

```sh
uv run python scripts/graphiv_manager/main.py              # [manager] PORT and STATE_PATH
uv run python scripts/graphiv_manager/main.py --port 3001  # a scratch copy beside the unit
uv run pytest tests/graphiv_manager -q
```

The state directory is `[manager] STATE_PATH` and is created on first start.
It holds `jobs/<id>/{job.json,log}`, `stats/<query>.json`, `rates.json` from finished stages, and one snapshot check per file.
Two managers on one state directory would both run jobs, so a scratch copy takes a directory of its own.
The stages connect as `PGUSER` when it is set, which is how the `graphiv-manager` unit writes tables its own user may only read.
