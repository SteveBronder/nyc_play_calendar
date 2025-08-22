from __future__ import annotations

"""Normalization utilities converting series to individual event instances."""

from datetime import datetime, timedelta
from typing import Iterable, List
from hashlib import md5
from zoneinfo import ZoneInfo

from .models import EventSeries, EventInstance, DEFAULT_DURATION

NY_TZ = ZoneInfo("America/New_York")


def generate_uid(title: str, start: datetime, venue: str) -> str:
    """Generate a deterministic UID based on title, start time and venue."""

    base = f"{title}-{start.isoformat()}-{venue}".encode("utf-8")
    return md5(base).hexdigest()


def expand_series(series: EventSeries, default_duration: timedelta = DEFAULT_DURATION) -> List[EventInstance]:
    """Expand an ``EventSeries`` into concrete ``EventInstance`` objects."""

    instances: List[EventInstance] = []
    for d in series.dates:
        for start_time in series.start_times:
            start = datetime.combine(d, start_time, NY_TZ)
            if series.end_time:
                end = datetime.combine(d, series.end_time, NY_TZ)
                if end <= start:
                    end += timedelta(days=1)
            else:
                end = start + default_duration
            uid = generate_uid(series.title, start, series.venue_name)
            instances.append(
                EventInstance(
                    uid=uid,
                    title=series.title,
                    description=series.description,
                    price=series.price,
                    venue_name=series.venue_name,
                    venue_address=series.venue_address,
                    start=start,
                    end=end,
                )
            )
    return instances
