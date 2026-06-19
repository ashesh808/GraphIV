# `phases/` — the pipeline, one phase per stage

Each phase does **strictly one thing**. Phases 1–5 are preprocessing; phase 6 is the live
endpoint. A phase is a self-contained directory with a uniform contract.

```
phases/
  global-config.json      data locations + endpoint APIs (shared; tracked)
  _framework.py           config resolution + dry-run + global-config access (shared)
  phase-<n>/
    run.py                entry point — the only thing you invoke
    config.json           this phase's parameters + component toggles
    components/           one module = one thing
      __init__.py
      <module>.py
```

## Running a phase

```bash
uv run python phases/phase-<n>/run.py [positionals] [flags]
```

Config resolution, highest priority first:
1. `--config=PATH` — read that JSON as the base (fails if missing/incomplete).
2. `--include-NAME` (binary → `true`) and `--set-NAME V` / `--set-NAME=V` (value, numbers
   coerced) — per-key overrides layered on the base. Hyphens in `NAME` map to `_` JSON keys.
3. `phases/phase-<n>/config.json` — the phase-local base used when `--config` is absent.

Every run:
- accepts `--dry-run` — prints the fully-resolved plan (components + params + artifacts) and exits
  without side effects;
- **always prints the resolved config** before doing work;
- is **idempotent** — re-running with the same config is a no-op on already-produced artifacts.

The component toggles **are** the ablation mechanism: an experiment is a config that turns
components on/off and records the result (see `../experiments/`).

## The phases

| phase | one thing | kind | produces |
|---|---|---|---|
| phase-1 | download PDFs | preproc | `data/pdf/<YYMM>/…`, SQLite metadata |
| phase-2 | acquire HTML | preproc | `data/html/<YYMM>/…`, `html_status` |
| phase-3 | labeled citation graph | preproc | Postgres `citation` (+intent/polarity) |
| phase-4 | graph store build | preproc | Neo4j graph + `paper_emb` vector index |
| phase-5 | semantic index build | preproc | topic tree (+ community summaries) |
| phase-6 | research endpoint | **endpoint** | grounded report + figures + `run.json` |

## Conventions
- `_framework.gpath(s)` resolves a global-config path (absolute as-is, else repo-relative).
- LLM health via `/v1/models` only; `/router/restart` to free VRAM; Gemma analytical/compose
  calls pass `enable_thinking:False`. One big model resident at a time (single 3090).
- Comments are one-line, specific, technical, non-trivial only.
