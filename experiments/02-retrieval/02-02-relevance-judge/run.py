"""experiment 02-02-relevance-judge — logic in code/relevance_judge.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from relevance_judge import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
