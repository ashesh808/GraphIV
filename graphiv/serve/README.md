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

## How a question picks its mode

`refine_question` returns candidates as `{question, mode}`, where `survey` means the lineage a
field is built on and `frontier` means what people are doing now. An interest that reads both
ways gets one candidate of each rather than a clarifying question, so the user's pick settles it
in one round trip instead of two.

`deep_research` takes that `mode` and resolves it through `_MODES` to `--set-rank joint` or
`--set-rank trajectory`. A client that sends no mode gets one classified from the question, and
anything unusable falls back to `survey`, since a mode never blocks a run.
