# 03-generation

Generation experiments: what the writer does with the papers it is given.

## Experiments

```
03-01-judge-validity        whether the judge agrees with a disjoint judge family
03-02-component-ablation    what each pipeline component contributes
03-03-embedding-format      sym plus HyDE against the asym space
03-04-recency-knob          how far the recency dial should be turned
03-05-frontier-pull         whether the year-filtered pull earns its cost
03-06-landmark-selection    how the landmark budget should be spent
03-07-graph-representation  which digest representation the writer reads best
03-08-judge-loop            how many judge rounds are worth running
03-09-critique-depth        how deep the per-paper critique should go
03-10-vision-figures        whether the figure gallery survives a caption check
03-11-hub-suppression       whether suppressing generic hubs helps or hurts
```

## Running one

```sh
uv run python experiments/03-generation/<name>/run.py
```

Each experiment writes into its own `results/` and `report/`, and its README carries the
hypothesis and the conclusion. Raw runs under `results/runs/` are gitignored.
