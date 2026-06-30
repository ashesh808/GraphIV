"""experiment 03-11-hub-suppression — logic in code/hub_suppression.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from hub_suppression import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
