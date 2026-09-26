"""
experiment 01-07-student-classifier, logic in src/classifier.py
"""

import sys

from src.classifier import run

if __name__ == "__main__":
    run("--no-cache" not in sys.argv[1:])
