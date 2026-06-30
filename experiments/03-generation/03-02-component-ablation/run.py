"""experiment 03-02-component-ablation — logic in code/component_ablation.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from component_ablation import run  # noqa: E402

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
