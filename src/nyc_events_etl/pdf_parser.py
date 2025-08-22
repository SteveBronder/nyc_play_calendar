"""PDF parsing utilities.

This module will parse curated PDF listings and return EventSeries objects.
The implementation is intentionally minimal for now.
"""

from __future__ import annotations

from typing import Iterable

from .models import EventSeries


def parse_pdf(path: str) -> Iterable[EventSeries]:
    """Parse a PDF file and yield event series.

    Args:
        path: Path to the input PDF.

    Returns:
        Iterable of EventSeries objects. Currently yields an empty list.
    """

    # Placeholder implementation.
    return []

