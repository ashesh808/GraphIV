"""
experiment 02-02-relevance-judge — logic in code/relevance_judge.py
"""

import sys
from pathlib import Path

# this tree's directory names are not identifiers, so the harness is reached by path
_EXPERIMENTS = next(p for p in Path(__file__).resolve().parents if p.name == "experiments")
sys.path.insert(0, str(_EXPERIMENTS))
sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from relevance_judge import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
