"""
experiment 01-02-labeling-quality, logic in src/labeling.py
"""

import sys

from src.labeling import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
