"""
experiment 01-05-topic-tree, logic in src/topictree.py
"""

import sys

from src.topictree import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
