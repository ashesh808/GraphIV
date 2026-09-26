# nix

The daemon as a package and as a NixOS module, which is how GraphIV is deployed.
The dev shell and the postgres helpers stay in `flake.nix`, since they are for working on the code
rather than for running it.

```
package.nix   the interpreter, the seven libraries the serve path imports, and the tree it runs from
module.nix    services.graphiv: the options, the generated config.toml, and the two units
```

## The package

`src/` is copied into `share/graphiv` and put on `PYTHONPATH` rather than installed, so it never
takes the name `src` in site-packages.
`bin/graphiv-serve` wraps `scripts/serve.py`, and the closure is 645 MB with no torch and no CUDA,
since every model the serve path uses is an endpoint it calls.

```sh
nix build .#graphiv
nix flake check          # the test suite, which needs no store and no GPU
```

## The module

```nix
{
  services.graphiv = {
    enable = true;
    database.dsn = "host=/run/graphiv port=5433 dbname=arxivkg";
    corpus.graph = "/Vault/graphiv/state/citation_graph_export.npy";
    corpus.html = "/mnt/corpus/html";   # optional, read only
    corpus.pdf = "/mnt/corpus/pdf";     # optional, read only
    endpoints.llm.name = "Gemma-4-26B";
    allowedHosts = [ "graphiv.example.com" ];
  };
}
```

`graphiv-api` on 6767 serves the nine tools.
`graphiv-frontend` on 6969 serves the dashboard from a second process carrying no tools at all, so
it opens neither the store nor the graph export and cannot reach the corpus.

The options name the deployment and nothing else. Every tuned constant lives in the recipe files
that ship with the package, because a Nix option is a promise to support whatever value is put
there, and a detuned retriever still reports numbers.

What the module does not do is provision postgres. It takes a dsn, and the cluster behind it needs
pgvector and the four tables the published dump restores. Reads are all the daemon ever issues, so
the role it connects as needs `CONNECT` and `SELECT` and nothing more.

## What a host has to supply

| | |
| --- | --- |
| the store | a postgres with pgvector, restored from the dump or built by `scripts/` |
| the graph export | `stage2_export_graph.py` writes it, and the dump does not carry it |
| two endpoints | a llama-server for embedding, any OpenAI compatible host for the model |
| the corpus, optionally | directories of `YYMM/<id>.html` and `YYMM/<id>v<n>.pdf` |

With no corpus, a paper is fetched from arXiv on the first read, one request every three seconds,
into the state directory. The corpus itself is always mounted read only.
