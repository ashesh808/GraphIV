# Legacy components

- [`research-webui/`](research-webui/README.md): the existing HTML/JavaScript report dashboard.
- [`nix/`](nix/README.md): the original Nix package and NixOS deployment module.
- `serve.py`: a compatibility launcher delegating to `apps.api.main`.

The dashboard remains available through `uv run graphiv-serve --http --role frontend`.
New frontend work belongs in [`apps/web`](../apps/web/README.md), and future cloud
infrastructure belongs in [`infra`](../infra/README.md).
