# _harness

The shared measurement instruments every experiment drives. Nothing here decides a result; it only produces one.

## Modules

```
runner.py        drive the endpoint for one condition, cached by question and config
driver.py        sweep conditions across topics, aggregate, write the artifacts
evaluate.py      the metric vector for one run
metrics.py       load a run, compute its metrics, render the table
judge.py         the multi-axis LLM judge
faithfulness.py  the faithfulness tripwire
vision_check.py  caption-faithfulness for the figure gallery
topics.py        the gold topic battery, canonical papers and spine
topics.json      the editable battery itself
viz.py theme.py tables.py   figures, palette and LaTeX tables
_llm.py _boot.py            endpoint client and the shared settings
```

The runner caches by a hash of question plus config, so an identical cell shared across two
experiments computes once.
