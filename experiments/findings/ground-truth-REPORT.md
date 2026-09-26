# Reference label set by three-way agreement

## Question

How to get ~1000 trustworthy intent labels without a human, after the previous file turned out to
be 944 of the shipped student's own predictions read back as truth.

## Method, as shipped

| step | detail |
| --- | --- |
| draw | `TABLESAMPLE SYSTEM(0.5)` over `v2.citations`, target present, sentence 30 to 1000 chars |
| student 1 | `student-v4`, DistilBERT with a linear head, seq 128, the model that wrote `citation_intent_v2` |
| student 2 | `data/citation_labeler/best.pt`, ModernBERT-base, seq 256, batch 32 |
| coverage | both students score every row, so no candidate is excluded for sitting outside one model's own top ranks |
| ranking | the product of the two probabilities, the joint score under independence |
| candidates | 300 per class, taken from rows where the two students agree |
| teacher | `best.txt` under Gemma-4-26B-Batched, 25 per call, an unparseable line kept as None rather than background |
| kept | rows all three call the same class, capped at 167 per class |

## Three runs

| | run 1 | run 2 | run 3, shipped |
| --- | --- | --- | --- |
| rows drawn | 100,000 | 337,772 | 339,718 |
| distinct sentences | 99,944 | 337,634 | 339,566 |
| scored by student 2 | 10,912 shortlist | 12,000 shortlist | all 339,566 |
| ranking | `min` | `min` | `product` |
| student agreement | 56.3% of shortlist | 58.5% of shortlist | 73.3% of everything |
| teacher unanswered | 86 | 134 | 75 |
| rows written | 885 | 942 | 985 |

The agreement figures measure different populations. A 2,000-per-class shortlist oversamples the
rare classes the two students argue about, while the full draw is roughly three quarters
`background`, which both call easily.

## Unanimous rows per class, run 3

| class | candidates | written |
| --- | --- | --- |
| uses | 300 | 167 |
| extends | 300 | 167 |
| compares | 300 | 167 |
| motivates | 174 | 150 |
| background | 300 | 167 |
| critiques | 300 | 167 |

## Output

`data/citation_labeler/ground_truth.csv`, 985 rows, columns `sentence`, `section`, `label`.
No empty sentences, no duplicate sentences, 41 rows with an empty section.

## Caveats

| caveat | detail |
| --- | --- |
| independence | both students were distilled from this teacher's prompt lineage, so their errors are correlated to an unmeasured degree |
| confidence bias | candidates are the highest joint-probability rows, so the set under-represents the hard cases a labeler gets wrong |
| motivates | 150 rather than 167, limited by how rarely the two students agree on that class |

## Files

| file | holds |
| --- | --- |
| `build.py` | the whole pipeline |
| `ground_truth_old.csv` | the previous file, 1,002 rows, 58 of them human |
| `ground_truth_885.csv`, `ground_truth_942.csv` | runs 1 and 2 |
