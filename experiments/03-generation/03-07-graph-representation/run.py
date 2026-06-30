"""experiment 03-07 — graph representation (logic in code/graph_representation{{,_phase2}}.py; --phase2 = axes phase)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

if __name__ == "__main__":
    use_cache = "--no-cache" not in sys.argv[1:]
    if "--phase2" in sys.argv[1:]:
        from graph_representation_phase2 import run
    else:
        from graph_representation import run
    run(use_cache)
