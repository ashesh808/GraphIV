"""experiment 03-03-embedding-format — logic in code/embedding_format.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from embedding_format import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
