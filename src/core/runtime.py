"""Environment overlays shared by local PostgreSQL and Azure deployments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.config import load_config


def runtime_config(path: str | Path) -> dict[str, Any]:
    """Resolve checked-in defaults, then explicit deployment settings.

    Legacy local configuration stays valid. Azure deployments never accidentally
    use the developer's PostgreSQL socket or loopback model services.
    """
    config = load_config(path)
    storage = config.setdefault("storage", {})
    cloud = os.environ.get("GRAPHIV_RUNTIME") == "azure"
    backend = os.environ.get(
        "GRAPHIV_STORAGE_BACKEND", "azure" if cloud else storage.get("BACKEND", "postgres")
    ).lower()
    cloud = cloud or backend == "azure"
    storage["BACKEND"] = backend
    if storage["BACKEND"] not in {"postgres", "sqlite", "azure"}:
        raise ValueError("GRAPHIV_STORAGE_BACKEND must be postgres, sqlite, or azure")
    storage["REPORT_BACKEND"] = os.environ.get(
        "GRAPHIV_REPORT_STORAGE_BACKEND",
        "azure" if cloud else storage.get("REPORT_BACKEND", "local")
    ).lower()
    if storage["REPORT_BACKEND"] not in {"local", "azure"}:
        raise ValueError("GRAPHIV_REPORT_STORAGE_BACKEND must be local or azure")
    endpoints = config.setdefault("endpoints", {})
    for env, key in (
        ("GRAPHIV_LLM_API_URL", "LLM_API"), ("GRAPHIV_LLM_MODEL", "LLM_NAME"),
        ("GRAPHIV_EMBED_API_URL", "EMBED_API"), ("GRAPHIV_EMBED_MODEL", "EMBED_NAME"),
    ):
        if cloud or env in os.environ:
            endpoints[key] = os.environ.get(env, "")
    for prefix in ("LLM", "EMBED"):
        endpoints[f"{prefix}_API_KEY"] = os.environ.get(f"GRAPHIV_{prefix}_API_KEY", "")
    endpoints["EMBED_QUERY_PREFIX"] = os.environ.get(
        "GRAPHIV_EMBED_QUERY_PREFIX", endpoints.get("EMBED_QUERY_PREFIX", "search_query: ")
    )
    database = config.setdefault("database", {})
    if "GRAPHIV_POSTGRES_DSN" in os.environ:
        database["PG_DEST"] = os.environ["GRAPHIV_POSTGRES_DSN"]
    elif cloud:
        database["PG_DEST"] = ""
    for env, block, key in (
        ("GRAPHIV_METADATA_PATH", storage, "METADATA_PATH"),
        ("GRAPHIV_INDEX_PATH", storage, "INDEX_PATH"),
        ("GRAPHIV_GRAPH_PATH", config["dataset"], "GRAPH_PATH"),
    ):
        if env in os.environ:
            block[key] = str(Path(os.environ[env]).resolve())
    serve = config["serve"]
    if cloud or "GRAPHIV_CACHE_PATH" in os.environ:
        root = Path(os.environ.get("GRAPHIV_CACHE_PATH", "/var/lib/graphiv/cache"))
        serve.update(CACHE_PATH=str(root / "llm"), RUNS_PATH=str(root / "runs"))
        config["dataset"].update(HTML_PATH=str(root / "html"), PDF_PATH=str(root / "pdfs"))
        storage["CACHE_PATH"] = str(root / "snapshots")
    if "GRAPHIV_ALLOWED_HOSTS" in os.environ:
        serve["ALLOWED_HOSTS"] = [
            one.strip() for one in os.environ["GRAPHIV_ALLOWED_HOSTS"].split(",") if one.strip()
        ]
    return config
