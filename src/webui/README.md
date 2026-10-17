# webui

The dashboard over past runs, served by the frontend role.
There is no build step and no framework, and the one dependency, the markdown renderer, is vendored.

```
index.html            the page layout and the slide-over panel
app.js                everything the page does, from the run library to the graph
style.css             the four palettes, light and dark, and the layout
icon.svg              the G mark
vendor/marked.min.js  the markdown renderer
```

## A Run

The front page lists every run as a card, with a search box and paging.
A run opens on six tabs, and the tab is part of the url, so `#/run/<slug>/graph` is a link you can send.

| Tab | What it shows |
| --- | --- |
| Report | a one-sentence answer over six numbered sections, with a rail that tracks where you are |
| Methods | the method table filtered by answer, and a grid of the answer pairs no paper tried |
| Papers | every paper the run touched, under nine filters |
| Graph | one lineage at a time, every citation among its papers in its intent color |
| Topics | the run's papers placed in the corpus topic tree, each topic with a bar split by role |
| Details | what the run did, what it cost, and what the citation check had to change |

| Section | What it holds |
| --- | --- |
| 1 Overview | the opening, which frames the question and how the answer has changed |
| 2 What the papers show | one tab per claim the review makes, argued from the papers behind it |
| 3 Methods | the table as the report wrote it, with a link into the Methods tab |
| 4 Current work | one tab per area, plus what has appeared against the answer since |
| 5 Open questions | one tab per area, read out of the papers' own limitations sections |
| 6 Disagreements | one paper telling another it is wrong, in the citing author's words |

An area that started from a paper lists that paper first, whatever grade the reader gave it.
A method column filters and crosses only when its kind is `choice`, since free text is unique per row.
A run written before columns carried their kind is read by which columns list options, which are exactly the choice ones.

Hovering a citation shows the paper's card, and clicking it opens the pdf in the panel, from the local store when it is there and from arXiv when it is not.

## On a Phone

Below 760px the page goes to one column and the panel fills the screen.
A back-to-top button appears after 600px of scrolling, since the report is long by design.

## Where the Data Comes From

The routes are in `src/mcp/dashboard.py`, and every one of them only reads: `/api/runs`, `/api/runs/{slug}`, `/files/{slug}/{name}` for the five files a run writes, and `/pdf/{arxiv_id}` from the local pdf store.
The page draws `report.json`, so nothing parses the markdown back apart.
A run's name is checked against what is on disk rather than joined onto the root, so no path can escape it.

## Looking at It

```sh
uv run python scripts/serve.py --http --role frontend
```

Then open `[serve] FRONTEND_PORT` from `config.toml`, 6969 by default.
For a scratch copy, give a copied config another port.
