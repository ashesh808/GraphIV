# mcp

The tools an outside agent calls.
The agent runs the loop and decides what to search next and when to stop, while the server holds the corpus and the tuned settings and answers one call at a time.

```
refine.py          turns a freeform interest into focused questions, each tagged survey or frontier
identify_areas.py  splits one question, or an author's or a list's papers, into the areas that need separate searches
retrieve.py        one area, or the field around a list of papers, into graded papers, plus an id for the ranking
mine.py            runs LeyLine over the papers a search kept
read_paper.py      a paper's full text at the depth asked for, or a schema the caller invented, filled in
write_report.py    the document, checked and written to disk
what_cites.py      who took a position on one paper, and the sentence they used
search_papers.py   plain cosine, to turn a title into an id
recall_paper.py    a description of what a paper did or argued into the papers that match it
find_runs.py       the reports this server already wrote, matched to a new question
server.py          registers the tools and serves both transports
state.py           what every tool opens once, and the rankings and areas kept between calls
effort.py          the quick, standard and deep presets
dashboard.py       the read-only routes the dashboard reads its runs from
```

## A Session

```
refine -> identify_areas -> retrieve per area -> mine -> read_paper -> write_report
```

`retrieve` keeps its ranking on the server and returns a `query_id`, since the ranking is thousands of papers and `mine` needs three hundred of them rather than the forty that come back.
Pass every earlier id as `seen`, and the reply carries `new_share`, the share of the new ranking nothing earlier found.
Two different areas share almost none of their top papers, while an area that was only renamed shares about a fifth.

## Modes

| Mode | Starts from | Answers |
| --- | --- | --- |
| `survey` | the question, or a paper | a wide net, weighted to what the field cites |
| `frontier` | the question, or a paper | a wide net, weighted to what the field is doing now |
| `consensus` | the question, or a paper | what the field's reviews agree on |
| `ancestry` | a paper | what led to it, which is survey with every forward term at 0 |
| `evolution` | a paper | what came of it, which is frontier with every ancestor term at 0 |

Starting from a paper uses its stored vector as the query, so it sits at a cosine of 1 and leads the kept list.
`arxiv_id` picks the paper, and without one it is the paper closest to the question inside the dates.
`date_min` and `date_max` bound every mode, and the floor cuts the ranking after scoring, so the retrieval itself does not change.

## What the Caller Cannot Set

The pool size, the gate, the era rule, how deep the reader reads, the walk settings and the exponents all live in `retrieval_recipes/*.toml`.
The caller picks a mode by name and never sees the numbers.

## Running It

```sh
uv run python scripts/serve.py                          # stdio
uv run python scripts/serve.py --http --role api        # the tools, 6767
uv run python scripts/serve.py --http --role frontend   # the dashboard, 6969
```

Both ports are in the `[serve]` block of `config.toml`, and `GRAPHIV_CONFIG` can point at another file.
The frontend role is a second server with no tools, so it never opens the store or the graph and cannot reach the corpus.
The graph export is about 400 MB and loads once at start, so the first question costs the same as the tenth.
