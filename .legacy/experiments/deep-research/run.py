"""
experiment deep-research, logic in src/deep_research.py
"""

import sys

from src.deep_research import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
