from __future__ import annotations

"""Scraper for The Public Theater calendar."""

import re
import time
from typing import Callable, List, Optional

from ..date_parsing import parse_dates, parse_times
from ..models import EventSeries


def _extract(block: str, cls: str) -> str:
    m = re.search(rf'<span class="{cls}">(.*?)</span>', block, re.S)
    return m.group(1).strip() if m else ""


def parse_html(
    html: str,
    year: int,
    fetch: Optional[Callable[[str], str]] = None,
    rate_limit: float = 0.0,
) -> List[EventSeries]:
    """Parse Public Theater events from HTML.

    ``fetch`` is an optional callable for retrieving individual event pages when
    additional details are missing from the listing. ``rate_limit`` enforces a
    delay between such fetches.
    """

    events: List[EventSeries] = []
    last_fetch = 0.0
    for block in re.findall(r'<div class="event">(.*?)</div>', html, re.S):
        title = _extract(block, "title")
        desc = _extract(block, "desc")
        date_str = _extract(block, "date")
        time_str = _extract(block, "time")
        price = _extract(block, "price")
        venue = _extract(block, "venue")
        address = _extract(block, "address")
        link_match = re.search(r'href="([^\"]+)"', block)
        source = link_match.group(1) if link_match else ""
        if fetch and source and (not desc or not price):
            now = time.time()
            wait = rate_limit - (now - last_fetch)
            if rate_limit and wait > 0:
                time.sleep(wait)
            page_html = fetch(source)
            last_fetch = time.time()
            desc = desc or _extract(page_html, "desc")
            price = price or _extract(page_html, "price")
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
                source=source,
            )
        )
    return events
