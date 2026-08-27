# External benchmarks: LitSearch and PaSa

Everything needed to compare GraphIV's retrieval against two published systems on a shared
protocol, in both directions: GraphIV on their benchmark, and their baselines on ours.

Read `FINDINGS.md` first for the verdict, `PROTOCOL.md` for what each benchmark actually
measures, and `BASELINES.md` for what it costs to reimplement their arms.

| path | what it is |
| --- | --- |
| `FINDINGS.md` | feasibility verdict, coverage numbers, protocol mismatches |
| `PROTOCOL.md` | both protocols, with the source of every claim marked |
| `BASELINES.md` | their baseline methods in enough detail to reimplement |
| `litsearch_mapped.jsonl` | 597 LitSearch queries with gold papers mapped to arXiv ids |
| `pasa_mapped.jsonl` | **not built**, the PaSa dataset is gated |
| `map_pasa.py` | builds `pasa_mapped.jsonl` once an HF token exists |
| `raw/litsearch/` | LitSearch queries, corpus ids and titles, eval code |
| `raw/pasa/` | the PaSa repo, no data |

## `litsearch_mapped.jsonl`

One row per LitSearch query, 597 rows.

| field | meaning |
| --- | --- |
| `query` | the query text, unmodified |
| `gold_arxiv_ids` | gold papers that resolve to an arXiv id present in `paper_meta` |
| `n_gold_original` | gold papers in the published benchmark |
| `n_gold_mapped` | how many of them survived the mapping |
| `gold_corpusids` | the original S2 corpusids, so a row can be traced back |
| `map_source` | `s2_arxiv_id` or `title_match`, per mapped id |
| `query_set`, `specificity`, `quality` | the benchmark's own labels, carried through |

A row with `n_gold_mapped == 0` is unscoreable here and must be dropped, not counted as a miss.

## Rebuilding

`raw/` is reproducible from the network with no credentials except for the PaSa data.
`map_pasa.py` needs `hf auth login` plus acceptance of the CarlanLark/pasa-dataset terms.
