"""
experiment 01-04-clustering-comparison — logic in code/clustering.py
"""

import sys
from pathlib import Path

# this tree's directory names are not identifiers, so the harness is reached by path
_EXPERIMENTS = next(p for p in Path(__file__).resolve().parents if p.name == "experiments")
sys.path.insert(0, str(_EXPERIMENTS))
sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from clustering import run

if __name__ == "__main__":
    _argv = sys.argv[1:]
    _n = int(_argv[_argv.index("--n") + 1]) if "--n" in _argv else 30000
    run("--no-cache" not in _argv, _n)
