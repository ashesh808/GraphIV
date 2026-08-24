# webui

The Research Library dashboard: an index of completed runs and a reading view for each one.

## Modules

```
__init__.py  the route registrar, and the only public entry point
pages.py     the two rendered pages, index and run
theme.py     the palettes, the stylesheet, the palette picker
scripts.py   every browser-side script, as string constants
runs.py      reading the run directory: the card list, the question, cache purging
```

Scripts and styles are inlined rather than served as files, because the page has no build
step. A read route registers on every instance; a mutating one is skipped entirely when the
process is readonly.
