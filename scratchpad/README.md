# scratchpad

Gitignored working space: one directory per task in flight, plus `.records/`.

When a task lands, its finding becomes one markdown file in `.records/`, named `<date>-<task>.md`, with its date, its setting, its results and how it was made.
Then the task directory is deleted.
`.records/` is the one part of this directory that is never deleted, and a record is never rewritten.
Anything that ships belongs in `src/` or `scripts/`.
