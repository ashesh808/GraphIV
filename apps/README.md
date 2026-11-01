# Applications

| Application | Responsibility | State |
| --- | --- | --- |
| [`api/`](api/README.md) | Runtime entrypoint, MCP transport, and research orchestration | Runs the existing backend |
| [`web/`](web/README.md) | Search saved research, read reports, and inspect papers and citation graphs | Next.js application |

Reusable tools and algorithms live in [`src/`](../src/README.md). The API serves the
existing static dashboard from [`legacy/research-webui/`](../legacy/research-webui/README.md).
The Next.js app reads the same run endpoints through its server, using `GRAPHIV_API_URL`
to select the backend. It includes clearly labelled examples for local use when the
default backend is unavailable. An explicitly configured connection shows errors.
The offline administration app and its browser assets live together in
[`offline/manager/`](../offline/manager/README.md).

Run `uv run graphiv-serve --http --role api` for the MCP endpoint or
`uv run graphiv-serve --http --role frontend` for the run endpoints and existing dashboard.
For the Next.js interface, follow [`apps/web`](web/README.md)'s local development commands.
Runtime settings come from [`configs/runtime.toml`](../configs/runtime.toml).
