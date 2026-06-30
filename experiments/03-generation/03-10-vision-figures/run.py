"""experiment 03-10-vision-figures — logic in code/vision_figures.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from vision_figures import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
