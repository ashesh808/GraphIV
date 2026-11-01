"""Command-line entrypoint for the MCP API and report dashboard."""

import argparse

from apps.api.server import run


def main() -> None:
    """Parse transport flags and start the requested server role."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--role", default="both", choices=["api", "frontend", "both"])
    parser.add_argument("--host", help="override the configured bind address")
    parser.add_argument("--port", type=int, help="override the configured HTTP port")
    args = parser.parse_args()
    run(http=args.http, role=args.role, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
