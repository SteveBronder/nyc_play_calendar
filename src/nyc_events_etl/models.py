"""Data models for normalized event information.

These dataclasses define the structure used throughout the pipeline. They are
minimal placeholders and will be extended as features are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional


@dataclass
class EventSeries:
    """A high level event which may occur on multiple dates or via a rule."""

    title: str
    description: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    price: str | None = None
    # Either a list of explicit datetimes or a textual recurrence rule.
    datetimes: List[datetime] = field(default_factory=list)
    rrule: str | None = None


@dataclass
class EventInstance:
    """Concrete occurrence of an event with a specific start/end time."""

    uid: str
    title: str
    start: datetime
    end: datetime
    description: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    price: str | None = None


def expand_series(series: EventSeries) -> Iterable[EventInstance]:
    """Expand a series into individual event instances.

    Currently this simply yields instances for each datetime listed and does not
    interpret recurrence rules. Future iterations will add full rule handling.
    """

    for dt in series.datetimes:
        uid = f"{hash((series.title, dt))}&@nyc-events"
        yield EventInstance(
            uid=uid,
            title=series.title,
            start=dt,
            end=dt,
            description=series.description,
            venue_name=series.venue_name,
            venue_address=series.venue_address,
            price=series.price,
        )

