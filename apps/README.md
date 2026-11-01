# Applications

| Application | Responsibility | State |
| --- | --- | --- |
| [`api/`](api/README.md) | Runtime entrypoint, MCP transport, and research orchestration | Runs the existing backend |
| [`web/`](web/README.md) | Future Next.js frontend | Directory scaffold |

Reusable tools and algorithms live in [`src/`](../src/README.md). The API serves the
existing static dashboard from [`legacy/research-webui/`](../legacy/research-webui/README.md).
The offline administration app and its browser assets live together in
[`offline/manager/`](../offline/manager/README.md).

Run `uv run graphiv-serve --http --role api` for the MCP endpoint or
`uv run graphiv-serve --http --role frontend` for the existing dashboard.
Runtime settings come from [`configs/runtime.toml`](../configs/runtime.toml).
