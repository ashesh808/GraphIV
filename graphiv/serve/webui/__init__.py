"""
The Research Library dashboard, served by the MCP http transport

Mutating routes are skipped entirely when readonly, so the public tunnel cannot reach one
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from starlette.requests import Request
    from starlette.responses import Response

from graphiv.serve.webui.pages import _index_html, _run_html
from graphiv.serve.webui.runs import _DATA_RE, _purge_caches, _run_question, _scan_runs
from graphiv.serve.webui.scripts import _ADMIN_JS

__all__ = ["register"]


def register(mcp: FastMCP, out: Path, readonly: bool = False) -> None:
    """
    Attach dashboard + action routes to the FastMCP starlette app (http transport)

        `readonly` = the GRAPHIV_READONLY public instance: only the read routes below the
        gate get registered, so mutation is absent from the process the tunnel can reach ,
        enforcement by topology, not by request inspection (the caddy 403s stay as a
        second layer). New READ routes go above the gate; anything mutating goes below.
    """
    from starlette.responses import (  # noqa: PLC0415
        HTMLResponse,
        JSONResponse,
    )
    from starlette.responses import (
        Response as StarletteResponse,
    )

    def _cfg_dir(request: Request) -> Path | None:
        slug = str(request.path_params["slug"])  # pyright: ignore[reportAny]
        cfg = str(request.path_params["cfg"])  # pyright: ignore[reportAny]
        d = (out / slug / cfg).resolve()
        if not str(d).startswith(str(out.resolve()) + "/") or not d.is_dir():
            return None
        return d

    def _is_public(request: Request) -> bool:
        # caddy sets this on the public vhost, and it is cosmetic since caddy enforces the 403s
        return request.headers.get("x-graphiv-public") is not None

    @mcp.custom_route("/", methods=["GET"])
    async def index(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        return HTMLResponse(_index_html(_is_public(request) or readonly))

    @mcp.custom_route("/api/runs", methods=["GET"])
    async def api_runs(_: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(_scan_runs(out))

    @mcp.custom_route("/run/{slug}/{cfg}", methods=["GET"])
    async def run_page(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return HTMLResponse("<h1>run not found</h1>", status_code=404)
        return HTMLResponse(
            _run_html(d.parent.name, d.name, _run_question(d), _is_public(request) or readonly)
        )

    @mcp.custom_route("/api/run/{slug}/{cfg}/graph-data", methods=["GET"])
    async def run_graph_data(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        """
        The embedded DATA json out of graph.html, lets the dashboard render the

                interactive graph (with the pdf sidebar) for runs generated before this UI.
        """
        d = _cfg_dir(request)
        if d is None or not (d / "graph.html").exists():
            return JSONResponse({"error": "no graph"}, status_code=404)
        m = _DATA_RE.search((d / "graph.html").read_text(encoding="utf-8"))
        if m is None:
            return JSONResponse({"error": "no DATA in graph.html"}, status_code=404)
        return StarletteResponse(m.group(1), media_type="application/json")

    if readonly:
        return

    @mcp.custom_route("/admin.js", methods=["GET"])
    async def admin_js(_: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        return StarletteResponse(_ADMIN_JS, media_type="application/javascript")

    @mcp.custom_route("/api/run/{slug}/{cfg}/delete", methods=["POST"])
    async def run_delete(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        await asyncio.to_thread(shutil.rmtree, d)
        if not any(d.parent.iterdir()):
            d.parent.rmdir()
        return JSONResponse({"ok": True, "deleted": f"{d.parent.name}/{d.name}"})

    @mcp.custom_route("/api/run/{slug}/{cfg}/purge-cache", methods=["POST"])
    async def run_purge(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        question = _run_question(d)
        if not question:
            return JSONResponse({"ok": False, "error": "no question in run meta"})
        return JSONResponse({"ok": True, "purged": _purge_caches(question)})

    @mcp.custom_route("/api/run/{slug}/{cfg}/compile-pdf", methods=["POST"])
    async def run_pdf(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        d = _cfg_dir(request)
        if d is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        if not (d / "report.tex").exists():
            return JSONResponse({"ok": False, "error": "no report.tex (single-pass run)"})
        # async subprocess: a blocking run here stalls FastMCP keepalives (event loop)
        try:
            proc = await asyncio.create_subprocess_exec(
                "latexmk",
                "-pdf",
                "-g",
                "-interaction=nonstopmode",
                "report.tex",
                cwd=d,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            return JSONResponse(
                {"ok": False, "error": "latexmk not on PATH (run in the dev shell)"}
            )
        try:
            out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        except TimeoutError:
            proc.kill()
            return JSONResponse({"ok": False, "error": "latexmk timed out (600s)"})
        ok = proc.returncode == 0 and (d / "report.pdf").exists()
        if not ok:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"latexmk exit {proc.returncode}",
                    "log": out_b.decode(errors="replace")[-3000:],
                }
            )
        return JSONResponse({"ok": True, "pdf": f"/files/{d.parent.name}/{d.name}/report.pdf"})
