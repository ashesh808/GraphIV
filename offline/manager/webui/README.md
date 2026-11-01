# Manager application

The administration interface for store health, pipeline jobs, benchmarks, and publishing.

```text
index.html   page layout
app.js       browser behavior and requests to the manager API
style.css    layout and palettes
icon.svg     application icon
```

Run `uv run python -m offline.manager` and open port 6868, or the `[manager] PORT` value in
[`configs/offline.toml`](../../../configs/offline.toml). This app has no build step.
Its routes and job orchestration live in the [offline manager](../README.md).
