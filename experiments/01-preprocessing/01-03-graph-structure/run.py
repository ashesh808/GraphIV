"""experiment 01-03-graph-structure — logic in code/graph.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from graph import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
