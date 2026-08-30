# docs

What the system is, why each choice was made, and how to run it.
Design notes live here; measurements live in `experiments/`, and the code's own structure is in
each package README.

```
preprocess.md    the build: what to supply, what to run in what order, how to check it landed
restore.md       skip the build, restore the published dump and serve from it
pipeline.md      how the whole thing works, one plain line per step
decisions.md     every choice, what it ran against, and the number that settled it
release-plan.md  the 2026-07-03 release status, kept as a record
future-plans.md  known defects, limitations and what comes next
tasks.md         the 2026-06-22 handoff, kept as a record
instructions.md  the single-store consolidation plan, kept as a record
audits/          finished write-ups that no experiment owns
```

`preprocess.md` and `restore.md` are finished and current.
The retrieval, MCP and experiment pages are next: `pipeline.md` sections 2 through 4,
`future-plans.md` and `instructions.md` all still describe the pre-rewrite store, and get
rewritten when the serve path is repointed at the new tables.
