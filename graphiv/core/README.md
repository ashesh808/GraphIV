# core

Shared services and data contracts, carrying no algorithms of their own. Every other subpackage may import from here, and this one imports from none of them.

## Modules

```
config.py    config.toml loading, typed sections, repo-relative path resolution
settings.py  the serve path's constants, resolved once from config
cli.py       the flag grammar every scripts/ entrypoint shares
models.py    the dataclasses that flow between stages
store.py     Postgres and pgvector access, the only SQL in the codebase
embed.py     the embedding-endpoint client
llm.py       the chat client, in async and sync form
router.py    router health, restart recovery, the dated system preamble
```

`settings.py` reads config once at import, so importing it opens no connection but does
require `config.toml` to exist.
