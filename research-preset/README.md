# research-preset

Named bundles of stage settings, so a run is a file rather than a line of flags.

Any key a `--set-<name>` flag would carry can live here instead. Resolution runs least specific
first: `[stage.<name>]` in `config.toml`, then the preset, then the flags on the command line.
So a preset changes the defaults and a flag still wins over it.

```
research-preset/
├── survey.toml      the lineage a field is built on
├── frontier.toml    what people are doing right now
├── quick.toml       a single pass, for a smoke test
└── eval.toml        the survey-qrels protocol, corpus capped and the survey hidden
```

Run one with `uv run python scripts/research.py "<question>" --preset survey`.
An unknown name fails fast and lists the presets that exist.
