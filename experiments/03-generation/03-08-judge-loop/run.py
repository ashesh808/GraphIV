"""
experiment 03-08-judge-loop — logic in code/judge_loop.py
"""

import sys
from pathlib import Path

# this tree's directory names are not identifiers, so the harness is reached by path
_EXPERIMENTS = next(p for p in Path(__file__).resolve().parents if p.name == "experiments")
sys.path.insert(0, str(_EXPERIMENTS))
sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from judge_loop import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
