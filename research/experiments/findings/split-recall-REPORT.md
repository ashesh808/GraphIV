# Does splitting a SurveyMatch query into areas improve recall

## What was asked

Whether the split into areas, with or without the reader, beats asking the written question whole,
at a budget of 1000 returned papers.

## The setup

| | |
| --- | --- |
| cases | 3 of the 300 in `experiments/retrieve/SurveyMatch/survey/scores.jsonl`, `Random(0)` |
| query | the one `GemmaWriter` wrote for the benchmark, not the abstract |
| key, cutoff, blocklist | the case's own, copied from the run that measured 0.812 |
| recipe | `survey.toml`, replayed here rather than read back |
| budget | 1000 returned papers in every arm |
| reader | the top 2000 of each ranking, 16 papers a call |
| stopped | the run was killed after 3 of 12 cases |

| arm | what it asks |
| --- | --- |
| whole | the written question, one pool |
| read_whole | whole, then the reader drops what it calls unrelated |
| keep_whole | whole, then the reader only demotes it |
| split | k areas, question pool plus anchor pool each, gate at 4, merged by rank |
| split_flat | the same without the gate |
| both | the whole ranking interleaved with the areas |
| read_split, keep_split | the reader over each area, graded against that area's question |

## Recall by budget, 3 cases

| arm | @100 | @200 | @500 | @1000 |
| --- | --- | --- | --- | --- |
| whole | 0.328 | 0.469 | 0.625 | 0.763 |
| read_whole | 0.287 | 0.393 | 0.635 | 0.716 |
| keep_whole | 0.287 | 0.393 | 0.635 | 0.716 |
| split | 0.244 | 0.314 | 0.485 | 0.614 |
| split_flat | 0.283 | 0.420 | 0.540 | 0.666 |
| both | 0.261 | 0.361 | 0.529 | 0.639 |
| read_split | 0.233 | 0.312 | 0.455 | 0.578 |
| keep_split | 0.233 | 0.312 | 0.455 | 0.578 |

The replayed `whole` arm reproduced the stored benchmark recall on every case.

## Per case at 1000

| case | key | k | reach | whole | split | split_flat | read_whole | read_split |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current Status of r-Process Nucleo | 216 | 3 | 0.866 | 0.639 | 0.556 | 0.593 | 0.611 | 0.546 |
| Thermodynamics of Quantum Coupled | 94 | 2 | 0.894 | 0.649 | 0.287 | 0.404 | 0.574 | 0.340 |
| Higher spin symmetry (breaking) in | 26 | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.962 | 0.846 |

## What the pools held

| case | pool whole | pool union | ceiling whole | ceiling union |
| --- | --- | --- | --- | --- |
| r-Process Nucleosynthesis | 6,263 | 26,469 | 0.639 | 0.866 |
| Quantum Coupled Transport | 8,998 | 27,694 | 0.691 | 0.894 |
| Higher spin symmetry | 8,210 | 22,524 | 1.000 | 1.000 |

## Findings

1) Splitting cost 0.15 recall at 1000 and lost on every budget.
2) The gate carried a third of that loss, since turning it off recovered 0.05.
3) The reader cost 0.05 at 1000 and gained 0.01 at 500, and dropping against demoting changed nothing.
4) The union of the area pools held 0.87 and 0.89 of the key where the single pool held 0.64 and 0.69.
