"""experiment 02-03-ancestor-gate — logic in code/ancestor_gate.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from ancestor_gate import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
