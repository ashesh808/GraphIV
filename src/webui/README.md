# webui

The dashboard over past runs, served by the frontend role of the same http transport the tools run on.
No build step, no node_modules and no framework.

```
index.html            the shell, the navbar and the slide-over panel
app.js                the library, the six tabs, the graph, the topic tree, the router and the theme
style.css             the four shunka-shuutou palettes, light and dark, and the layout
icon.svg              the wordmark, a G in a circle in the accent
vendor/marked.min.js  the markdown renderer, vendored rather than fetched at runtime
```

## A run

The library is a search box, a pager and one card per run.
A run opens on six tabs, and the tab is in the url, so `#/run/<slug>/graph` is a link someone can send.

| tab | what it is for |
| --- | --- |
| Report | a one-sentence answer over six numbered sections, with a rail that tracks where you are |
| Methods | the method table filtered by answer, and a grid of the answer pairs no paper tried |
| Papers | every paper the run touched, under nine filters |
| Graph | one line at a time, picked by tabs named for the lines, every citation among its papers in its intent color |
| Topics | the run's papers placed in the corpus topic tree, each topic with its count and a bar split by role |
| Details | what the run did, what it cost, and what the grounding guard had to change |

| section | holds |
| --- | --- |
| 1 Overview | the opening, which frames the question and how the answer has moved |
| 2 What the papers show | one tab per claim the review makes, each argued from the papers that carry it |
| 3 Methods | the table as the report wrote it, and a link into the Methods tab |
| 4 Current work | one tab per area, plus what has appeared against the answer since |
| 5 Open questions | one tab per area, read out of the papers' own limitations sections |
| 6 Disagreements | one paper telling another it is wrong, in the citing author's words |

An area whose search started from a paper lists that paper first, whatever the reader graded it.
A method column filters and crosses only when its kind is `choice`, since a free text answer is unique per row.
A run written before columns carried their kind is read by which columns list options, which are exactly the choice ones.

Hovering a citation anywhere shows the paper's card.
Clicking one opens the panel, which shows the pdf from the local store when it is there and arXiv's own pdf when it is not.

## On a phone

Below 760px the layout goes to one column and the panel takes the whole screen.
A back-to-top button appears after 600px of scrolling, because the report is long by design.

## Where the data comes from

`src/mcp/dashboard.py` mounts read-only routes: `/api/runs`, `/api/runs/{slug}`, `/files/{slug}/{name}` for the five files a run writes, and `/pdf/{arxiv_id}` out of the local pdf store.
`report.json` is what the page draws, so nothing here parses the markdown back apart.
A run's name is checked against what is on disk rather than joined onto the root, so no path escapes it, and nothing here writes.

## Looking at it

```sh
uv run python scripts/serve.py --http --role frontend
```

Then open the `[serve] FRONTEND_PORT` from `config.toml`, 6969 by default.
A scratch copy belongs on another port, which is one line of a copied config.
