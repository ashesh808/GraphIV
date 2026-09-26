"""
Runs the GraphIV MCP server over stdio, or over streamable-http with --http

The graph export is loaded once at start, so the first question is as fast as the tenth
"""

from __future__ import annotations

import sys

from src.mcp.server import run

if __name__ == "__main__":
    run(http="--http" in sys.argv[1:])
