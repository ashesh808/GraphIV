# survey-consensus

Whether agreement among several human surveys on one topic is a cleaner answer key than any one
survey's reference list.

## Construction

| item | rule |
| --- | --- |
| surveys | survey-titled, stage 4, dated 2023-01 or later, title 25 to 130 chars |
| group | one anchor plus its 4 nearest surveys by `embed_full` cosine, within 18 months |
| membership | every peer at cosine >= 0.80 of the anchor, and each survey in at most one group |
| cutoff | the earliest date in the group, applied to both the key and retrieval |
| key at n | targets cited by at least n of the 5, resolved, stage 4, dated on or before the cutoff |
| query | the anchor's title with the survey boilerplate stripped |
| retrieval | cosine 5,000, one citation hop each way off the top 200, fuse at hub 0.3 |

| quantity | value |
| --- | --- |
| surveys considered | 3,556 |
| surveys with 25 or more resolved references | 2,197 |
| disjoint groups at cosine >= 0.80 | 17 |
| candidates per group | 7,615 to 13,656 |

## Recall of the n-of-5 agreement key

Groups whose key at that n is empty are excluded, which is why n=5 reads 11.

| n | groups | key size | in candidate pool | @100 | @200 | @500 | @1000 | @2000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 17 | 452.3 | 0.849 | 0.139 | 0.223 | 0.358 | 0.460 | 0.545 |
| 2 | 17 | 98.2 | 0.967 | 0.323 | 0.449 | 0.606 | 0.689 | 0.754 |
| 3 | 17 | 38.1 | 0.981 | 0.489 | 0.600 | 0.732 | 0.786 | 0.827 |
| 4 | 17 | 13.2 | 0.980 | 0.625 | 0.743 | 0.845 | 0.887 | 0.906 |
| 5 | 11 | 6.0 | 1.000 | 0.642 | 0.717 | 0.786 | 0.865 | 0.880 |

## P(a held out survey cites it | k of its 4 nearest peers cite it)

Same survey pool, one member held out instead of all five voting.

| peer cosine | groups | k>=1 | k>=2 | k>=3 | k>=4 |
| --- | --- | --- | --- | --- | --- |
| 0.85+ | 22 | 0.160 | 0.394 | 0.561 | 0.716 |
| 0.80 | 135 | 0.145 | 0.377 | 0.547 | 0.493 |
| 0.75 | 384 | 0.100 | 0.303 | 0.465 | 0.311 |
| 0.70 | 592 | 0.079 | 0.271 | 0.394 | 0.237 |
| below 0.70 | 1,063 | 0.035 | 0.148 | 0.196 | 0.100 |

| peer cosine | papers at k>=3 | held out survey's own references | recall |
| --- | --- | --- | --- |
| 0.85+ | 26.4 | 135.3 | 0.120 |
| 0.80 | 16.2 | 144.7 | 0.072 |
| 0.75 | 9.7 | 123.3 | 0.044 |

## Files

| file | does |
| --- | --- |
| `main.py` | the held out precision table |
| `agree.py` | the n-of-5 recall table |
| `out.json`, `agree.json` | per-group values behind both |
