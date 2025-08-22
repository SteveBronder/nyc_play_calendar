"""Command-line entry point for the NYC Events ETL.

This module orchestrates parsing events from multiple sources, expanding them
into individual instances and optionally syncing with Google Calendar.  It also
provides logging utilities used by the CLI.
"""

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Iterable, Optional, List

from . import normalization, pdf_parser
from .google_calendar import GoogleCalendarClient
from .models import EventInstance, EventSeries
from .scrapers import frigid, public_theater


class _ErrorWatcher(logging.Handler):
    """Handler that notes if any error-level log was emitted."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.had_error = False

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - tiny
        if record.levelno >= logging.ERROR:
            self.had_error = True


def configure_logging(
    *, verbose: bool = False, log_file: str = "nyc_events.log"
) -> tuple[logging.Logger, _ErrorWatcher]:
    """Configure logging with a rotating file handler.

    The log level defaults to INFO but can be overridden by setting the
    ``NYC_EVENTS_LOG_LEVEL`` environment variable.  ``--verbose`` on the CLI
    forces DEBUG level.
    """

    level_name = os.getenv("NYC_EVENTS_LOG_LEVEL", "DEBUG" if verbose else "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("nyc_events_etl")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    watcher = _ErrorWatcher()
    logger.addHandler(watcher)

    return logger, watcher


def _expand_events(series: Iterable[EventSeries]) -> List[EventInstance]:
    events: List[EventInstance] = []
    for s in series:
        events.extend(normalization.expand_series(s))
    return events


def run_etl(dry_run: bool = False, gc_client: Optional[GoogleCalendarClient] = None) -> None:
    """Run the ETL pipeline and log stats for each source."""

    logger = logging.getLogger("nyc_events_etl")
    all_events: List[EventInstance] = []

    sources = [
        ("PDF", lambda: pdf_parser.parse_pdf("events.pdf", 2025, 1)),
        ("Frigid", lambda: frigid.parse_html("", 2025)),
        ("Public Theater", lambda: public_theater.parse_html("", 2025)),
    ]

    for name, parser in sources:
        try:
            series = parser()
        except Exception:  # pragma: no cover - exercised in integration
            logger.exception("Failed to parse %s", name)
            series = []
        events = _expand_events(series)
        logger.info(
            "%s: %d series parsed, %d instances expanded",
            name,
            len(series),
            len(events),
        )
        all_events.extend(events)

    inserted = updated = deleted = 0
    if gc_client and not dry_run:
        for event in all_events:
            action = gc_client.upsert_event(event)
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
        logger.info("Google Calendar: %d inserted, %d updated, %d deleted", inserted, updated, deleted)
    else:
        logger.info("Google Calendar: %d inserted, %d updated, %d deleted", inserted, updated, deleted)


def raise_on_error(watcher: _ErrorWatcher) -> None:
    """Raise ``SystemExit(1)`` if the watcher observed any errors."""

    if watcher.had_error:
        raise SystemExit(1)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        prog="nyc-events",
        description="NYC Events ETL CLI.",
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
    """Run the CLI."""

    args = parse_args(argv)
    _, watcher = configure_logging(verbose=args.verbose)
    run_etl(dry_run=args.dry_run)
    raise_on_error(watcher)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()

