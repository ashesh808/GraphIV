# British spelling detection over `scripts/`

## Ask

Detect British spellings in the rewritten preprocessing code with an NLP library rather than by eye,
then run it systematically over `scripts/`.

## Configuration

| component | version | role |
| --- | --- | --- |
| `spacy` | 3.8.16 | `blank("en")` tokenizer, splits prose into words with offsets |
| `breame` | 0.1.2 | British-American lexicon, covers inflections |
| `wordfreq` | 3.1.1 | corpus frequency, validates a suffix rewrite |
| `tokenize` | stdlib | splits a python file into comment, string and identifier spans |

No spacy pipeline model is installed and `en_core_web_sm` is not on PyPI, so the tokenizer runs
without a tagger.

## Decision order per word

| step | rule | outcome |
| --- | --- | --- |
| 1 | length < 4, or in `IGNORE` | skip |
| 2 | in `SUPPLEMENT` | flag, 20 words breame lacks |
| 3 | `british_spelling_exists` | flag with `get_american_spelling` |
| 4 | suffix pattern `-ise` `-yse` `-our` | flag only if `zipf(guess) > zipf(word)` |

## Effect of the frequency gate on the suffix patterns

| word | rewrite | zipf word | zipf rewrite | verdict |
| --- | --- | --- | --- | --- |
| quantised | quantized | 1.09 | 2.27 | flag |
| neutralises | neutralizes | 1.55 | 2.27 | flag |
| normalised | normalized | 2.55 | 3.27 | flag |
| distil | distill | 2.04 | 2.47 | flag |
| excised | excized | 2.58 | 0.00 | reject |
| otherwise | otherwize | 4.88 | 0.00 | reject |
| precise | precize | 4.13 | 0.00 | reject |
| surprise | surprize | 4.75 | 1.79 | reject |
| exercise | exercize | 4.68 | 1.05 | reject |

A fixed floor of 1.0 admitted `surprize` and `exercize`. The ratio rule rejects both.

## Recall, control file

`control/known_british.py` plants 27 British spellings across an identifier, a docstring, a comment
and a string literal.

| span kind | planted | caught |
| --- | --- | --- |
| identifier | 8 | 8 |
| comment | 6 | 6 |
| string, docstring included | 13 | 13 |

## Findings in `scripts/`

| file | line | span | word | rewrite | state |
| --- | --- | --- | --- | --- | --- |
| `citation_labeler/README.md` | 8 | text | distil | distill | fixed |
| `citation_labeler/stage2_train_student.py` | 2 | docstring | distil | distill | fixed |
| `citation_preprocess/matcher.py` | 742 | comment | backwards | backward | fixed |

Re-run after the fixes: 0 findings over the 26 files in `scripts/`.

## Findings elsewhere in the repo, not touched

| directory | findings | files |
| --- | --- | --- |
| `experiments/` | 19 | 15 |
| `graphiv/` | 8 | 7 |
| `docs/` | 6 | 4 |
| `tests/` | 1 | 1 |
| `CLAUDE.md` | 1 | 1 |

| word | count | where |
| --- | --- | --- |
| towards | 7 | generated reports, `docs/`, experiment results |
| normalised, normalisation | 4 | `graphiv/retrieve`, `graphiv/preprocess`, experiment READMEs |
| neighbours, neighbouring | 5 | `graphiv/retrieve`, `graphiv/generate` |
| judgement | 3 | `experiments/03-generation`, `docs/decisions.md` |
| grey | 3 | one generated report |
| analyses | 3 | generated reports, `docs/audits` |
| behaviour | 2 | `tests/README.md`, `CLAUDE.md` |
| backwards, afterwards | 4 | `graphiv/preprocess`, `docs/` |
| quantised | 2 | generated reports |
| neutralises | 1 | `graphiv/retrieve/readers.py` |
| distil | 1 | `docs/decisions.md` |

11 of the 35 sit inside LLM generated reports under `experiments/`, which are records of a run and
not editable text.

## Known limitation

`analyses` is the plural of `analysis` and the British third person of `analyse`, and telling them
apart needs a POS tag. With no pipeline model the detector flags both, so the three hits above are
unverified.

## Running it

```sh
uv run --with breame --with wordfreq python scratchpad/british-detector/main.py scripts
uv run --with breame --with wordfreq python scratchpad/british-detector/main.py graphiv docs
```
