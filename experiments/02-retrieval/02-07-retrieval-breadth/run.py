"""experiment 02-07-retrieval-breadth — logic in code/breadth_budget.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from breadth_budget import run  # noqa: E402

if __name__ == "__main__":
    run()
