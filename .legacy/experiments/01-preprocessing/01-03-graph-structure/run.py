"""
experiment 01-03-graph-structure, logic in src/graph.py
"""

import sys

from src.graph import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
