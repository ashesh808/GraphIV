"""
Runs the GraphIV MCP server over stdio, or over streamable-http with --http

The graph export is loaded once at start, so the first question is as fast as the tenth
The frontend role serves the dashboard alone, which needs neither the store nor the graph
"""

from __future__ import annotations

from apps.api.main import main

if __name__ == "__main__":
    main()
