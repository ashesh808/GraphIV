# _reports

The ten deep reports that `03-01` through `03-04` measure, five questions written twice, once
with the citation digest and once without.

They live here rather than in `output/research/` because they are evidence, not library
entries: `output/research/` holds what people submit through the MCP, and anything there is
free to be deleted. Each experiment's `cache/reports.txt` names the ones it scored.

```
_reports/
├── how-did-neural-machine-translation-deve-.../   survey
├── what-are-the-foundational-architectures-.../   survey
├── what-are-researchers-doing-right-now-to-.../   frontier
├── what-is-the-current-state-of-the-art-in-.../   frontier
└── what-are-the-newest-approaches-to-conti-.../   frontier
```

Each slug holds two config directories, one per digest, and each of those is a full run:
`report.md`, `run.json`, `papers.json`, `digest.txt` and the figures.
