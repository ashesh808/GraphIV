# mcp

The tool surface an outside agent drives. The loop belongs to the caller, so nothing here decides
what to search next or when to stop, and every constant that was tuned against a benchmark stays
on this side of the wire.

```
refine.py           a freeform interest into focused questions, each tagged survey or frontier
identify_areas.py   one question into the areas that must be searched separately
retrieve.py         one area into graded papers, and an id for the ranking behind them
mine.py             a set of papers into what the field argues with and how it got there
read_paper.py       full text, at the depth asked for, into a schema the caller invented
write_report.py     the document, grounded and written to disk
what_cites.py       who took a position on one paper, and the sentence they used
search_papers.py    plain cosine, to turn a title into an id
server.py           the registrations and both transports
state.py            the handles, and the rankings kept between calls
effort.py           quick, standard and deep
```

## The shape of a session

```
refine -> identify_areas -> retrieve per area -> mine -> read_paper -> write_report
```

`retrieve` returns a `query_id` and keeps the ranking here, because it is thousands of papers and
`mine` needs three hundred of them rather than the forty that come back. Pass every earlier id as
`seen` and the reply carries `new_share`, the share of the new ranking nothing earlier found.
Measured: two genuinely different areas share none of their heads, and an area renamed rather than
changed shares a fifth of it.

## What the caller cannot set

The seed, the gate exponent, the era rule, how deep the reader reads, the walk parameters and the
scoring exponents. Those live in `retrieval_recipes/*.toml`, and `mode` picks one file which gives
a matched scorer and miner. The caller picks the mode by name, never the numbers.

## Running it

```sh
uv run python scripts/serve.py          # stdio
uv run python scripts/serve.py --http   # streamable-http on GRAPHIV_MCP_PORT, default 8756
```

The graph export is 400 MB and is loaded once at start, so the first question costs the same as
the tenth.
