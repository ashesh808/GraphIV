"""
experiment 01-01-resolver-quality, logic in src/resolver.py
"""

import sys

from src.resolver import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
