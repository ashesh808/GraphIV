# Storage

Storage adapters shared by the runtime library.
`runs.py` reads the persisted research-run metadata and report files used by MCP tools
and the legacy dashboard.

FAISS and SQLite adapters will be added here once their schemas and loading lifecycle
are specified. Offline index construction belongs in [`offline/index_build`](../../offline/index_build/README.md).
