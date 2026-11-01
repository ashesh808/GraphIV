# Flash attention 2 for ModernBERT inference

## Question

Whether FA2 is worth moving this repo to Python 3.14 and torch 2.13, the only versions the
prebuilt wheel in `ModernLayoutLM/wheelhouse` can load into.

## Configuration

| item | value |
| --- | --- |
| model | `answerdotai/ModernBERT-base`, 6 labels, bfloat16 |
| input | 4,096 real citation sentences from `v2.citations`, as `(section, sentence)` pairs |
| batch | 32, seq cap 256 |
| environment | ModernLayoutLM, Python 3.14, torch 2.13.0 cu13, flash_attn 2.8.3.post1 |
| gpu | RTX 3090 at 22.7 of 24.5 GB, shared with llama-router and a running labeling job |
| method | four cells back to back in one process, 4 warmup batches each, `cuda.synchronize` around the timed loop |

## Result

| backend | padding | rows/s | against baseline |
| --- | --- | --- | --- |
| sdpa | max_length | 176 | 1.00x |
| sdpa | dynamic | 338 | 1.92x |
| flash_attention_2 | max_length | 134 | 0.76x |
| flash_attention_2 | dynamic | 193 | 1.10x |

Absolutes for the two sdpa rows are derived from the measured ratios and the two directly
observed FA2 rates, which agree to within 0.5%. The card was contended throughout, so the
ratios are the reliable part and the absolutes are a floor.

## Reading

| finding | number |
| --- | --- |
| FA2 against sdpa, same padding | 0.76x and 0.57x |
| dynamic padding against max_length, same backend | 1.92x on sdpa, 1.44x on FA2 |
| positions wasted padding a citation sentence to 256 | see the run header |

