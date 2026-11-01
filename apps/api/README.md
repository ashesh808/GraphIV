# API application

Python HTTP and MCP entrypoint, intended for Azure Container Apps.

```text
main.py            command-line configuration
server.py          MCP registrations and stdio/HTTP transports
dashboard.py       HTTP routes for the retained legacy research UI
orchestration.py   reserved for the upcoming research workflow coordinator
Dockerfile         runtime-only container image
```

Tool implementations live in [`src/mcp`](../../src/mcp/README.md), and reusable research
logic lives in [`src`](../../src/README.md). The application uses
[`configs/runtime.toml`](../../configs/runtime.toml), or the file named by `GRAPHIV_CONFIG`.

```sh
uv run graphiv-serve --http --role api
uv run python -m apps.api --http --role api --host 0.0.0.0 --port 8000
```

The existing research loop remains driven by the MCP caller. The new coordinator and cloud
service connections will be implemented after the architecture is specified.

Build the container from the repository root with
`docker build -f apps/api/Dockerfile -t graphiv-api .`.
Mount a deployment-specific config with writable data paths and set `GRAPHIV_CONFIG` when running it.
The container installs runtime dependencies only; training and research dependencies are separate groups.
