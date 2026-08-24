# serve

Everything that exposes a finished run to a caller.

## Modules

```
mcp_server.py  the MCP tools, the file routes, both transports
webui/         the Research Library dashboard
```

## Running it

```sh
uv run python scripts/serve.py          # stdio
uv run python scripts/serve.py --http   # streamable-http plus the dashboard
```

In production this is the `graphiv-mcp` systemd unit, which also brings Postgres up.
Setting `GRAPHIV_READONLY=1` registers no tool and no mutating route, which is what the
public vhost reaches.
