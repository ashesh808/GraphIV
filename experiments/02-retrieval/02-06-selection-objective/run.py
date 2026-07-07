"""experiment 02-06-selection-objective — logic in code/selection_objective.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from selection_objective import run  # noqa: E402

if __name__ == "__main__":
    run()
