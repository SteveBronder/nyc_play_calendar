from __future__ import annotations

"""Parser for the curated PDF list of NYC events."""

import re
from pathlib import Path
from typing import List

from .date_parsing import parse_dates, parse_times
from .models import EventSeries

EVENT_RE = re.compile(
    r"^"  # start
    r"(?P<title>.+?)\s+–\s+"  # title
    r"(?P<description>.+?);\s*"  # description up to first semicolon
    r"(?P<time>[^;]+);\s*"  # time expression
    r"(?P<dates>[^–]+)\s+–\s+"  # date expression
    r"(?P<price>[^–]+)\s+–\s+"  # price
    r"(?P<venue>[^–]+)\s+–\s+"  # venue
    r"(?P<address>.+)$"  # address
)


def parse_pdf(path: str | Path, year: int, month: int) -> List[EventSeries]:
    """Parse the Blankman-style PDF into ``EventSeries`` objects.

    Parameters
    ----------
    path:
        Path to the PDF file.
    year, month:
        Calendar context used when an entry omits an explicit month (e.g.
        "first Sunday of every month").
    """

    try:  # local import to allow tests to run without the dependency
        import pdfplumber  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency missing
        raise ImportError("pdfplumber is required for PDF parsing") from exc

    events: List[EventSeries] = []
    with pdfplumber.open(str(path)) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
    raw_events = [e.strip() for e in text.split("\n\n") if e.strip()]
    for entry in raw_events:
        m = EVENT_RE.match(entry)
        if not m:
            continue
        data = m.groupdict()
        start_times, end_time = parse_times(data["time"])
        dates = parse_dates(data["dates"], year, default_month=month)
        events.append(
            EventSeries(
                title=data["title"],
                description=data["description"],
                price=data["price"],
                venue_name=data["venue"],
                venue_address=data["address"],
                dates=dates,
                start_times=start_times,
                end_time=end_time,
            )
        )
    return events
