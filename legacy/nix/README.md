# Legacy Nix deployment

The retained package and NixOS module for the existing deployment.
The developer shell and PostgreSQL helpers remain in the root [`flake.nix`](../../flake.nix).
Azure infrastructure has its separate reserved location under [`infra/azure/`](../../infra/azure/README.md).

```
package.nix   the tree the daemons run from, and the wrappers that start them over a uv venv
module.nix    services.graphiv: the cluster, the three units, and generated settings in the store
```

## The package

Nix supplies the interpreter, uv and the native libraries the wheels load, and no Python package.
Every Python dependency comes from `uv.lock`, the same file the dev shell's `.venv` is synced from, so what runs deployed is what the code was run against.

`apps/`, `src/`, `offline/`, `research/`, `legacy/`, `configs/`, `retrieval_recipes/`, `pyproject.toml`, `uv.lock` and `.python-version` are copied into `share/graphiv`.
The wrappers put `share/graphiv` on `PYTHONPATH`, so the `src`, `apps`, and `offline` packages are available without installing the project. The existing browser dashboard is served from `legacy/research-webui/`; the manager serves its own `offline/manager/webui/` assets.

| wrapper | runs |
| --- | --- |
| `bin/graphiv-sync` | `uv sync --frozen --no-install-project` into `GRAPHIV_VENV`, on the package's own `python313` |
| `bin/graphiv-serve` | `python -m apps.api` on that venv |
| `bin/graphiv-manager` | `python -m offline.manager` on that venv |

`graphiv-manager` is a wrapper supplied by this legacy Nix package. In a development
checkout, run the manager with `uv run python -m offline.manager`; the runtime Python
wheel excludes offline and research code.

`GRAPHIV_VENV` defaults to `$XDG_STATE_HOME/graphiv/venv`, and the module sets it to `venvDir`.
The wrappers put `/run/opengl-driver/lib`, libstdc++, zlib and libGL on `LD_LIBRARY_PATH`, which is where a manylinux wheel expects them on any other distribution.
uv never downloads an interpreter and rebuilds the venv whenever it was made with another one, so a nixpkgs bump that moves `python313` moves the venv with it.
The dev shell sets `UV_PYTHON` to that same interpreter, so `.venv` and the deployed venv sit on one Python.

```sh
nix build .#graphiv
GRAPHIV_VENV=/tmp/graphiv-venv ./result/bin/graphiv-sync
```

## The module

`settings` combines the keys represented by [`configs/runtime.toml`](../../configs/runtime.toml)
and [`configs/offline.toml`](../../configs/offline.toml). The module writes one deployment
TOML file with absolute paths and gives it to every unit. Every key has a default,
so a host names only what differs.

```nix
{
  services.graphiv = {
    enable = true;
    stateDir = "/srv/graphiv";
    settings.endpoints.LLM_NAME = "Gemma-4-26B";
    settings.serve.ALLOWED_HOSTS = [ "graphiv.example.com" ];
  };
}
```

| unit | port | holds |
| --- | --- | --- |
| `graphiv-pg` | socket only | the cluster, one postmaster of its own |
| `graphiv-venv` | | a oneshot running `graphiv-sync` into `venvDir`, which every unit below requires |
| `graphiv-api` | `serve.API_PORT`, 6767 | the ten tools, the store, the graph export |
| `graphiv-frontend` | `serve.FRONTEND_PORT`, 6969 | the dashboard, from a second process registering no tools |
| `graphiv-manager` | `manager.PORT`, 6868 | the snapshot fetch and every preprocess stage, on the GPU |
| `graphiv-graph` | | a path unit restarting the api when the graph export is rewritten |

The frontend opens neither the store nor the graph export, so it cannot reach the corpus.
The manager writes the store and the corpus, so it belongs on a private vhost only.

`stateDir` and `dataDir` are the layout, and every path in `settings` defaults under one of them:

```
<stateDir>/venv          the venv uv fills from uv.lock, torch and its CUDA wheels included
<stateDir>/data          the snapshot, the models, the graph export and the cluster
<stateDir>/data/export   the manager's store dumps and Parquet releases
<stateDir>/data/arxiv    the corpus, as trees of YYMM/<id>.html and YYMM/<id>v<n>.pdf
<stateDir>/cache         model replies keyed by their prompt, safe to delete at any time
<stateDir>/runs          one directory per report written
<stateDir>/manager       the manager's jobs, logs and cached charts
```

Point `settings.dataset.HTML_PATH` and `PDF_PATH` at their resolved paths when the full text is on another mount.
A symlink under `dataDir` leaves every unit ordering on the wrong mount, which turns every full-text read into a silent miss.

`postgres.enable` runs the cluster under `postgres.dataDir`, created by `initdb` when it holds no `PG_VERSION`, and `postgres.settings` reaches the server as `-c` flags.
Turn it off to point `settings.database.PG_DEST` at a cluster run elsewhere.
The api and the frontend only ever read, so their role needs `CONNECT` and `SELECT`.
The stages insert, truncate and copy, so `manager.databaseUser` names the role that owns the four tables when it is not the unit's own user.
The manager's path carries `postgres.package` for the dump stage, and with `postgres.enable` off, `manager.path` has to name a `pg_dump` no older than the cluster.
`manager.huggingface.tokenFile` is the file holding the Hugging Face token the publish stage uploads with, such as a sops secret, and systemd hands it to the manager's unit alone as a credential.
Name it as a string, since a path literal copies the token into the store.
`settings.export.DATA_REPO`, `CITATION_REPO` and `SURVEY_REPO` say where it publishes, and an empty one is skipped.

No option names a tuned constant.
The exponents and the `[miner]` block live in the recipe files that ship with the package, because an option is a promise to support whatever value is put there, and a detuned retriever still reports numbers.

## What a host has to supply

| | |
| --- | --- |
| network on the first sync | PyPI, for the wheels `uv.lock` names, cached under `CACHE_PATH/uv` |
| the store | the dump restored into the cluster, or built by the manager from a snapshot |
| the graph export | the manager's last stage writes it, and the dump does not carry it |
| two endpoints | a llama-server for embedding, any OpenAI compatible host for the model |
| a GPU, for the manager | the two classifiers load onto it, and `manager.path` carries `nvidia-smi` |
| the corpus, optionally | the two trees above, which the manager's stages fill |

With no corpus, a paper is fetched from arXiv on the first read, one request every three seconds, into those same trees, so the second read is local.
Set `settings.serve.FETCH = false` when they cannot be written, and the daemon then answers out of whatever is already there.
