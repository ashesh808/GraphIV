# `experiments/` — numbered, self-contained investigations

Each experiment answers one question by driving the `phases/` (usually phase-6 with component
toggles flipped) or by standalone probe/benchmark code, and records what it found. Experiments
are where visualizations, comparisons, ablations, and failed attempts live — **not** in the
pipeline.

```
experiments/
  experiment-<n>/
    code/        scripts that run the experiment (may import from ../../phases)
    results/     outputs: metrics.json, plots, sample reports
    README.md    what the experiment tests, how to run it, and the finding
```

## Index

| n | experiment | drives | status |
|---|---|---|---|
| 1 | autonomous-AI-research deep run | phase-6 `--effort deep` | planned |
| 2 | component ablation sweep | phase-6 toggles (`--include-graph/-cluster`, `--set-rank`) | planned |
| 3 | community-summary retrieval tier on/off | phase-5 `--include-summaries` + phase-6 | planned |

Earlier scratchpad work (parser/throughput benchmarks, resolver diagnostics, the trajectory
quality/APE/Pareto grid) is being re-homed here as numbered experiments.

## Convention
An experiment is reproducible: its `README.md` states the exact `run.py` invocation (config or
flags) so the result can be regenerated. Report a **vector** of metrics, never one alone — any
single metric is gameable (e.g. dropping the citation graph maximizes the frontier count by
discarding all structure).
