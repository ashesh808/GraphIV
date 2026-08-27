"""
experiment 01-04-clustering-comparison, logic in src/clustering.py
"""

import sys

from src.clustering import run

if __name__ == "__main__":
    _argv = sys.argv[1:]
    _n = int(_argv[_argv.index("--n") + 1]) if "--n" in _argv else 30000
    run("--no-cache" not in _argv, _n)
