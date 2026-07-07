"""experiment 02-05-reader-fusion — logic in code/reader_fusion.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from reader_fusion import run  # noqa: E402

if __name__ == "__main__":
    run()
