# Configuration

| File | Used by |
| --- | --- |
| [`runtime.toml`](runtime.toml) | HTTP/MCP application and production library |
| [`offline.toml`](offline.toml) | Preprocessing, training, exports, research evaluation, and the manager |

The files are independent. Paths ending in `_PATH` resolve relative to their config file,
so `../data` and `../retrieval_recipes` keep their existing repository locations.
The offline config writes evaluation results into `../research/experiments`.

Set `GRAPHIV_CONFIG` for an application or manager configuration override. Offline stages
also accept `--config_path`; their default is this directory's `offline.toml`.
Use deployment-specific absolute paths for application data and model/index locations.
