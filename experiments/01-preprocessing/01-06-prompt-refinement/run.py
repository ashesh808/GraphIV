"""
experiment 01-06-prompt-refinement, logic in src/refinement.py
"""

import sys

from src.refinement import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
