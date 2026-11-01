"""
The read-only routes the dashboard runs on, which are the run directory and the static page

A run's facts come out of its own run.json, so listing the library reads no report
"""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from src.core.fetch import pdf_file
from src.core.paths import PROJECT_ROOT
from src.storage.runs import FILES, known, read_one, read_runs

LOG = logging.getLogger(__name__)

HERE = PROJECT_ROOT / "legacy" / "research-webui"
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


def mount(mcp: FastMCP, root: Path, pdfs: Path, fetch: bool = False) -> None:
    """
    Registers the dashboard on the http transport, which serves nothing that writes

    Args:
        mcp: The server.
        root: The directory runs are written to.
        pdfs: The pdf store, which the reading panel shows a paper out of.
        fetch: Whether a paper the store never had may be fetched from arXiv.
    """

    @mcp.custom_route("/api/runs", methods=["GET"])
    async def listing(request: Request) -> Response:
        """
        Every run, for the library

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The rows as json.
        """
        _ = request
        return JSONResponse(read_runs(root))

    @mcp.custom_route("/api/runs/{slug}", methods=["GET"])
    async def one(request: Request) -> Response:
        """
        One run and its document

        Args:
            request: The http request, whose path carries the run's name.

        Returns:
            The run as json, or a 404.
        """
        found = read_one(root, str(request.path_params.get("slug", "")))
        if found is None:
            return JSONResponse({"error": "no such run"}, status_code=404)
        return JSONResponse(found)

    @mcp.custom_route("/", methods=["GET"])
    async def page(request: Request) -> Response:
        """
        The dashboard itself

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The page.
        """
        _ = request
        return FileResponse(HERE / "index.html", media_type=TYPES[".html"])

    @mcp.custom_route("/style.css", methods=["GET"])
    async def styles(request: Request) -> Response:
        """
        The stylesheet

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The file.
        """
        _ = request
        return FileResponse(HERE / "style.css", media_type=TYPES[".css"])

    @mcp.custom_route("/app.js", methods=["GET"])
    async def script(request: Request) -> Response:
        """
        The dashboard script

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The file.
        """
        _ = request
        return FileResponse(HERE / "app.js", media_type=TYPES[".js"])

    @mcp.custom_route("/vendor/marked.min.js", methods=["GET"])
    async def markdown(request: Request) -> Response:
        """
        The markdown renderer the page draws a report with

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The file.
        """
        _ = request
        return FileResponse(HERE / "vendor/marked.min.js", media_type=TYPES[".js"])

    @mcp.custom_route("/icon.svg", methods=["GET"])
    async def icon(request: Request) -> Response:
        """
        The wordmark, a G in a circle in the palette's own accent

        Args:
            request: The http request, which carries nothing this reads.

        Returns:
            The file.
        """
        _ = request
        return FileResponse(HERE / "icon.svg", media_type=TYPES[".svg"])

    @mcp.custom_route("/files/{slug}/{name}", methods=["GET"])
    async def download(request: Request) -> Response:
        """
        One of a run's own files, for the download menu

        Args:
            request: The http request, whose path carries the run and the file.

        Returns:
            The file, or a 404.
        """
        slug = str(request.path_params.get("slug", ""))
        name = str(request.path_params.get("name", ""))
        found = root / slug / name
        if not known(root, slug) or name not in FILES or not found.is_file():
            return JSONResponse({"error": "no such file"}, status_code=404)
        return FileResponse(found)

    @mcp.custom_route("/pdf/{arxiv_id:path}", methods=["GET", "HEAD"])
    async def paper(request: Request) -> Response:
        """
        One paper's pdf out of the local store, which the reading panel shows inline

        A paper the store never had is fetched when this instance is allowed to, and is
        otherwise a 404 that the page turns back into an arXiv link.

        Args:
            request: The http request, whose path carries the arXiv id.

        Returns:
            The pdf, or a 404.
        """
        found = pdf_file(pdfs, str(request.path_params.get("arxiv_id", "")), fetch)
        if found is None:
            return JSONResponse({"error": "not in the local store"}, status_code=404)
        return FileResponse(found, media_type="application/pdf")

    LOG.info("dashboard mounted over %s", root)
