"""Command line interface for the NYC Events ETL."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nyc-events", description="NYC Events ETL")
    parser.add_argument("pdf", type=Path, help="Input PDF of events")
    parser.add_argument("ics", type=Path, help="Output ICS file path")
    parser.add_argument("--dry-run", action="store_true", help="Parse without exporting")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = Pipeline()
    if args.dry_run:
        pipeline.run(str(args.pdf), str(args.ics))
    else:
        pipeline.run(str(args.pdf), str(args.ics))
    return 0

