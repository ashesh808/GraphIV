# download

Metadata to files on disk, behind the `Downloader` class. Every method is one idempotent operation over the shared SQLite metadata database and the file stores.

## Modules

```
downloader.py  the Downloader: wiring only
seed.py        Kaggle metadata refresh, idempotent by remote zip size
pdf.py         PDF acquisition from GCS via aria2c
html.py        LaTeXML HTML acquisition, plus the one-shot dump migration
fetch.py       on-demand per-paper fetch at serve time, local store first
_common.py     config bridge and the id-to-path helpers
```

## Column ownership

`publication.downloaded` belongs to `pdf.py` and `publication.html_status` to `html.py`.
Neither is ever cross-written.

## Running it

```sh
uv run python scripts/seed.py --dry-run
uv run python scripts/download_pdf.py [--include-metadata-only]
uv run python scripts/download_html.py [--include-migrate]
```
