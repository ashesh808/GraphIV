"""experiment 03-05-frontier-pull — logic in code/frontier_pull.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from frontier_pull import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
