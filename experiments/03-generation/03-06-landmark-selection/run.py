"""experiment 03-06-landmark-selection — logic in code/selection.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from selection import run  # noqa: E402

if __name__ == "__main__":
    run()
