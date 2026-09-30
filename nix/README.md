# nix

The daemon as a package and as a NixOS module, which is how GraphIV is deployed.
The dev shell and the postgres helpers stay in `flake.nix`, since they are for working on the code rather than for running it.

```
package.nix   the interpreter, the libraries it imports, and the tree it runs from
module.nix    services.graphiv: the cluster, the three units, and config.toml in the store
```

## The package

`src/`, `scripts/` and `retrieval_recipes/` are copied into `share/graphiv` and put on `PYTHONPATH` rather than installed, so `src` never takes that name in site-packages.

| output | wraps | carries |
| --- | --- | --- |
| `graphiv` | `bin/graphiv-serve`, `scripts/serve.py` | the serve path, no torch and no CUDA |
| `graphiv-manager` | `bin/graphiv-manager`, `scripts/graphiv_manager/main.py` | the serve path plus torch, transformers, umap-learn and scikit-learn |

The manager variant is `graphiv.override { withManager = true; }`.
Its torch is the upstream CUDA 13 wheel, since a CUDA torch built from source is hours of compile and the binary cache carries no CUDA variant.

```sh
nix build .#graphiv
nix build .#graphiv-manager
nix flake check          # the test suite, which needs no store and no GPU
```

## The module

`settings` is `config.toml`, one attribute per key, and every key has a default, so a host names only what differs.

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
| `graphiv-api` | `serve.API_PORT`, 6767 | the nine tools, the store, the graph export |
| `graphiv-frontend` | `serve.FRONTEND_PORT`, 6969 | the dashboard, from a second process registering no tools |
| `graphiv-manager` | `manager.PORT`, 6868 | the snapshot fetch and every preprocess stage, on the GPU |
| `graphiv-graph` | | a path unit restarting the api when the graph export is rewritten |

The frontend opens neither the store nor the graph export, so it cannot reach the corpus.
The manager writes the store and the corpus, so it belongs on a private vhost only.

`stateDir` and `dataDir` are the layout, and every path in `settings` defaults under one of them:

```
<stateDir>/data          the snapshot, the models, the graph export and the cluster
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

No option names a tuned constant.
The exponents and the `[miner]` block live in the recipe files that ship with the package, because an option is a promise to support whatever value is put there, and a detuned retriever still reports numbers.

## What a host has to supply

| | |
| --- | --- |
| the store | the dump restored into the cluster, or built by the manager from a snapshot |
| the graph export | the manager's last stage writes it, and the dump does not carry it |
| two endpoints | a llama-server for embedding, any OpenAI compatible host for the model |
| a GPU, for the manager | the two classifiers load onto it, and `manager.path` carries `nvidia-smi` |
| the corpus, optionally | the two trees above, which the manager's stages fill |

With no corpus, a paper is fetched from arXiv on the first read, one request every three seconds, into those same trees, so the second read is local.
Set `settings.serve.FETCH = false` when they cannot be written, and the daemon then answers out of whatever is already there.
