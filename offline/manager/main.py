"""
Serves the manager: one page that runs every preprocessing script, one job at a time

Stopping it sends the running job SIGINT and waits, so a stage rolls back rather than dying midway
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette

from offline.manager.routes import routes
from offline.manager.schedule import Manager
from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG, PROJECT_ROOT

# how long a stop waits on a stage before uvicorn gives up, which covers a COPY rolling back
STOP_SECONDS = 600


def main() -> None:
    """
    Reads the flags, builds the manager and serves it until stopped
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument(
        "--config_path",
        default=os.environ.get("GRAPHIV_CONFIG") or str(OFFLINE_CONFIG),
    )
    _ = ap.add_argument(
        "--scripts", default=str(PROJECT_ROOT / "offline"), help="the offline pipeline directory"
    )
    _ = ap.add_argument("--state", help="the directory this owns, [manager] STATE_PATH by default")
    _ = ap.add_argument("--host", help="[serve] HOST by default")
    _ = ap.add_argument("--port", type=int, help="[manager] PORT by default")
    args = ap.parse_args()
    config = Path(str(args.config_path)).resolve()
    said: dict[str, Any] = load_config(config)
    state = Path(str(args.state or said["manager"]["STATE_PATH"])).resolve()
    host = str(args.host or said["serve"]["HOST"])
    port = int(args.port or said["manager"]["PORT"])

    # the state directory is shared with the graphiv group, so what this writes stays group writable
    _ = os.umask(0o002)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    manager = Manager(
        scripts=Path(str(args.scripts)).resolve(),
        config=config,
        state=state,
        python=sys.executable,
    )

    @asynccontextmanager
    async def life(app: Starlette) -> AsyncGenerator[None]:
        _ = app
        await manager.start()
        yield
        await manager.stop()

    app = Starlette(routes=routes(manager), lifespan=life)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        timeout_graceful_shutdown=STOP_SECONDS,
    )


if __name__ == "__main__":
    main()
