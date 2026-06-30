"""experiment 03-08-judge-loop — logic in code/judge_loop.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from judge_loop import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
