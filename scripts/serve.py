"""
Run the GraphIV MCP server over stdio, or over streamable-http with --http

The http transport also serves the run artifacts and the Research Library dashboard.
"""

from __future__ import annotations

import sys

from graphiv.serve.mcp_server import run

if __name__ == "__main__":
    run(http="--http" in sys.argv[1:])
