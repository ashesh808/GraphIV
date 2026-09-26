# webui

The dashboard over past runs, served by the same http transport the MCP tools run on. No build
step, no node_modules and no framework.

```
index.html            the shell, the navbar and the slide-over panel
app.js                the library, the four tabs, the graph, the router and the theme
style.css             the four shunka-shuutou palettes, light and dark, and the layout
icon.svg              the wordmark, a G in a circle in the accent
vendor/marked.min.js  the markdown renderer, vendored rather than fetched at runtime
```

## The two views

The library is a search box, a pager and one card per run. A run opens on four tabs, and the tab is
in the url, so `#/run/<slug>/graph` is a link someone can send.

| tab | what it is for |
| --- | --- |
| Report | the review, in six numbered sections with a rail that tracks where you are |
| References | every paper the run touched, filtered and sorted by relevance, date, closeness or how argued with |
| Graph | the whole run plotted, time across and closeness up, the paths over it and each one readable below |
| Details | what the run did, what it cost, and what the grounding guard had to change |

The report reads top to bottom and never hides anything behind a click that a reader would have to
guess at. Where one section holds several things at one depth, they share the space as a strip over
one panel rather than as more scrolling.

| section | holds |
| --- | --- |
| 1 What this is about | the opening, which frames the question and how the answer has moved |
| 2 What we know | one tab per claim the review makes, each argued from the papers that carry it |
| 3 The methods | the table, how the methods spread along each axis, and the combinations nobody published |
| 4 Active research | one tab per area, plus what has appeared against the answer since |
| 5 Unanswered questions | one tab per area, read out of the papers' own limitations sections |
| 6 Where the field disagrees | one paper telling another it is wrong, at most two per paper so it spans the field |

Hovering a citation anywhere shows the paper's card. Clicking one opens the panel, which shows
the pdf from the local store when it is there and the abstract when it is not.

## The graph

Deterministic, so it never wiggles: publication date across, closeness to the question up, the dot
sized by how often the paper is cited and colored by what the reader called it. A gold line is an
edge on a path the walk reproduced. The legend toggles a role, the selector isolates one path, and
the search box dims everything that does not cite or is not cited by what it found.

Under the chart every path is written out as a dated list, since a trajectory is a claim about how
the field moved and a reader wants to check it paper by paper. Isolating one there redraws the
chart around it.

## On a phone

Below 760px the rail becomes a sticky strip of numbers above the sections, the sub-tabs stack full
width, the reference rows go vertical and the panel takes the whole screen. The chart is laid out
when its own tab opens rather than at load, since a hidden panel measures zero and the chart would
otherwise size itself for a desktop and force a sideways scroll. A back-to-top button appears after
600px of scrolling, because the report is long by design.

## Where the data comes from

`src/mcp/dashboard.py` mounts read-only routes: `/api/runs`, `/api/runs/{slug}`,
`/files/{slug}/{name}` for the five files a run writes, and `/pdf/{arxiv_id}` out of the local pdf
store. `report.json` is what the page draws, so nothing here parses the markdown back apart. A run's name is checked against what is on disk rather than joined onto the root, so no
path escapes it, and nothing here writes.

## Looking at it

```sh
uv run python scripts/serve.py --http --role frontend
```

Then open the `[serve] FRONTEND_PORT` from `config.toml`, 6969 by default.
A scratch copy belongs on another port, which is one line of a copied config.
