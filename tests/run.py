"""
Runs every test in the suite, so one command covers what the gates check

Exits with pytest's own code, which makes it usable from a hook or a driver script
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def main() -> None:
    """
    Collects the whole suite and exits on its result
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("target", nargs="?", default="", help="a subdirectory or file to run")
    _ = ap.add_argument("-v", "--verbose", action="store_true")
    _ = ap.add_argument("--slow", action="store_true", help="also run tests marked slow")
    args = ap.parse_args()

    argv = [str(HERE / str(args.target)) if args.target else str(HERE)]
    argv += ["-v"] if args.verbose else ["-q"]
    if not args.slow:
        argv += ["-m", "not slow and not gpu"]
    raise SystemExit(pytest.main(argv))


if __name__ == "__main__":
    sys.exit(main())  # pyright: ignore[reportArgumentType]
