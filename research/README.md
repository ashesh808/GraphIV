# Research and evaluation

```text
recipe_tuning/  ranking evaluation and recipe fitting
experiments/    published experiments, findings, and benchmark outputs
assets/         research figures and their generators
themes/         plotting styles and fonts
```

These components are excluded from the application wheel and container image.
Use [`configs/offline.toml`](../configs/offline.toml) for data, benchmark, and output paths.
Historical experiment artifacts preserve the paths and settings recorded when they were produced.

```sh
uv run python research/recipe_tuning/stage2_evaluate.py --split test
uv run python research/assets/run.py
```
