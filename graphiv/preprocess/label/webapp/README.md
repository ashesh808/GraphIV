# webapp

The citation labeling app: the sentence shown inside its own paper, with both endpoints resolved.

Desktop layout only, since the job is reading a PDF page beside a form.

```
__init__.py  the queue, the Postgres lookups, the routes and the server
page.py      the single page, assembled like the dashboard's shell
theme.py     the stylesheet, in the dashboard's idiom and variable names
script.py    the browser half: fetch an item, paint it, take the keystroke
```

The PDF work lives one level up in `../pdfview.py`, which picks the page by word-gram overlap
because a PDF breaks lines mid-phrase and a substring search misses.

## Running it

```sh
uv run python scripts/doomscroll.py --pdf --port 6767
```

Labels append to `data/citation_labels/gold_labels.jsonl` in the same shape the keyboard tool
writes, so `scripts/doomscroll.py --to-pg <file>` pushes either into `gold_label`.
