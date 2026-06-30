**Known-fact accuracy: 1.0** (true 1.0, false-topic 1.0, false-subtle 1.0; n=24).

| degradation | full wins | tie | variant wins | axis |
|---|--:|--:|--:|---|
| identical | 0/3 | 3/3 | 0/3 | sanity/position |
| truncated_75 | 3/3 | 0/3 | 0/3 | coverage |
| truncated_50 | 3/3 | 0/3 | 0/3 | coverage |
| truncated_25 | 3/3 | 0/3 | 0/3 | coverage |
| citations_stripped | 3/3 | 0/3 | 0/3 | grounding |
| shuffled | 3/3 | 0/3 | 0/3 | lineage (reorder) |
| chronology_corrupted | 1/3 | 2/3 | 0/3 | lineage (year-flip) |
| verbose_pad | 0/3 | 3/3 | 0/3 | verbosity |

- position bias (non-tie on identical): 0/6 (CLEAN)
- verbosity bias (verbose_pad wins): 0/3 (none)
