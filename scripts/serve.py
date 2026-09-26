"""
Runs the GraphIV MCP server over stdio, or over streamable-http with --http

The graph export is loaded once at start, so the first question is as fast as the tenth
The frontend role serves the dashboard alone, which needs neither the store nor the graph
"""

from __future__ import annotations

import argparse

from src.mcp.server import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--http", action="store_true")
    _ = ap.add_argument("--role", default="both", choices=["api", "frontend", "both"])
    args = ap.parse_args()
    run(http=bool(args.http), role=str(args.role))
