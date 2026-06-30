"""experiment 03-09-critique-depth — logic in code/critique_depth.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from critique_depth import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
