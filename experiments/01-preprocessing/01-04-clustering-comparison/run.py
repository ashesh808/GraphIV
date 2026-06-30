"""experiment 01-04-clustering-comparison — logic in code/clustering.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from clustering import run  # noqa: E402

if __name__ == "__main__":
    _argv = sys.argv[1:]
    _n = int(_argv[_argv.index("--n") + 1]) if "--n" in _argv else 30000
    run("--no-cache" not in _argv, _n)
