"""MCP server for GraphIV — one tool: deep_research(question) -> the finished report markdown.

Thin by design: each call shells out to run.py (a crash or CUDA OOM kills the run, not the
server) and returns report.md. A single-slot lock serializes runs — one 3090, one PG, one
model resident at a time. Runs are synchronous (a deep run is minutes, within MCP tool-call
budgets); figures land next to the report on disk and are referenced by relative path.

    uv run python phases/phase-6/serve_mcp.py          # stdio transport (librechat etc.)
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_HERE = Path(__file__).resolve().parent
_RUN = _HERE / "run.py"
_DONE = re.compile(r"done -> (\S+/report\.md)")

mcp = FastMCP("graphiv")
_slot = threading.Lock()


@mcp.tool()
def deep_research(question: str, effort: int = 4) -> str:
    """Run GraphIV deep research: a grounded, cited literature review over all of arXiv.

    effort 0-5 trades latency for depth (3+ = judge-driven deep loop with full-PDF critique
    and figures; a deep run takes minutes). Every arXiv id cited in the result exists in the
    corpus. Returns the review as markdown.
    """
    effort = max(0, min(5, effort))
    with _slot:
        proc = subprocess.run(
            [sys.executable, str(_RUN), question, f"--set-effort={effort}"],
            capture_output=True,
            text=True,
            timeout=7200,
        )
    m = None
    for m in _DONE.finditer(proc.stdout):
        pass  # keep the last "done ->" (the deep loop logs intermediate rounds)
    if m is None:
        tail = (proc.stdout + proc.stderr)[-2000:]
        return f"ERROR: run produced no report (exit {proc.returncode}).\n\n{tail}"
    return Path(m.group(1)).read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()
