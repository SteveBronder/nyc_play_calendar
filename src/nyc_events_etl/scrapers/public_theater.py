from __future__ import annotations

"""Scraper for The Public Theater calendar."""

import re
import time
import urllib.request
from datetime import datetime
from typing import Any, List

from ..date_parsing import parse_dates, parse_times
from ..models import EventSeries


def _extract(block: str, cls: str) -> str:
    m = re.search(rf'<span class="{cls}">(.*?)</span>', block, re.S)
    return m.group(1).strip() if m else ""


def parse_html(html: str, year: int) -> List[EventSeries]:
    """Parse Public Theater events from HTML."""

    events: List[EventSeries] = []
    for block in re.findall(r'<div class="event">(.*?)</div>', html, re.S):
        title = _extract(block, "title")
        desc = _extract(block, "desc")
        date_str = _extract(block, "date")
        time_str = _extract(block, "time")
        price = _extract(block, "price")
        venue = _extract(block, "venue")
        address = _extract(block, "address")
        start_times, end_time = parse_times(time_str)
        dates = parse_dates(date_str, year)
        events.append(
            EventSeries(
                title=title,
                description=desc,
                price=price,
                venue_name=venue,
                venue_address=address,
                dates=dates,
                start_times=start_times,
                end_time=end_time,
            )
        )
    return events


def fetch_events(session: Any | None = None, sleep_secs: float = 1.0) -> List[EventSeries]:
    """Fetch and parse Public Theater events with throttling."""

    if session is None:
        with urllib.request.urlopen("https://example.com/public") as resp:  # pragma: no cover - network
            html = resp.read().decode("utf-8")
    else:
        resp = session.get("https://example.com/public")
        resp.raise_for_status()
        html = resp.text
    events = parse_html(html, datetime.now().year)
    time.sleep(sleep_secs)
    return events
