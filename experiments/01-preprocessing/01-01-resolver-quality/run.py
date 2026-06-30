"""experiment 01-01-resolver-quality — logic in code/resolver.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from resolver import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
