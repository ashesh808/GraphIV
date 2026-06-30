"""experiment 02-01-subgraph-retrieval — logic in code/subgraph_quality.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from subgraph_quality import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
