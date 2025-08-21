"""Command-line entry point for the NYC Events ETL.

This module provides a minimal CLI stub so Poetry can create the console script.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional list of raw arguments. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="nyc-events",
        description="NYC Events ETL CLI (stub).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to Google Calendar.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    """Run the CLI.

    Args:
        argv: Optional list of raw arguments. If None, uses sys.argv[1:].
    """
    args = parse_args(argv)
    print("NYC Events ETL CLI stub running.")
    print(f"dry_run={args.dry_run}, verbose={args.verbose}")
    sys.exit(0)


if __name__ == "__main__":
    main()
