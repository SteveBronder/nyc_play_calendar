from __future__ import annotations

"""Data models for NYC Events ETL."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional


@dataclass
class EventSeries:
    """Represents an event that may occur on multiple dates or times.

    The parser for any source (PDF or HTML) should create an ``EventSeries``
    instance.  The ``dates`` field contains the explicit dates for the event;
    recurring rules should be expanded into concrete dates before creating the
    dataclass.  ``start_times`` holds one or more start times for the event on a
    given date.  If ``end_time`` is ``None`` a default duration may be applied
    during normalization.
    """

    title: str
    description: str
    price: str
    venue_name: str
    venue_address: str
    dates: List[date]
    start_times: List[time]
    end_time: Optional[time] = None


@dataclass
class EventInstance:
    """Concrete single occurrence of an event.

    ``EventInstance`` objects are produced from ``EventSeries`` instances during
    normalization.  They contain fully specified start and end datetimes ready
    to be exported to ICS or sent to Google Calendar.
    """

    uid: str
    title: str
    description: str
    price: str
    venue_name: str
    venue_address: str
    start: datetime
    end: datetime


DEFAULT_DURATION = timedelta(hours=1)
"""Fallback duration used when an event lacks an explicit end time."""
