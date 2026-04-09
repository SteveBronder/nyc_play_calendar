from __future__ import annotations

"""Data models for NYC Events ETL."""

from dataclasses import dataclass, field
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
    during normalization.  ``source`` stores the URL the event was scraped from
    for later attribution or debugging.
    """

    title: str
    description: str
    price: str
    venue_name: str
    venue_address: str
    dates: List[date]
    start_times: List[time]
    end_time: Optional[time] = None
    source: str = ""
    theater_id: str = ""
    theater_name: str = ""
    production_id: str = ""
    ticket_url: str = ""
    schedule_source_url: str = ""
    raw_schedule_text: str = ""
    schedule_granularity: str = "instance"


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
    theater_id: str = ""
    theater_name: str = ""
    production_id: str = ""
    source: str = ""
    ticket_url: str = ""


@dataclass
class TheaterProduction:
    """Normalized production-level record used for JSON/site output."""

    production_id: str
    theater_id: str
    theater_name: str
    title: str
    description: str = ""
    price: str = ""
    venue_name: str = ""
    venue_address: str = ""
    source_url: str = ""
    ticket_url: str = ""
    schedule_source_url: str = ""
    raw_schedule_text: str = ""
    run_range_text: str = ""
    schedule_granularity: str = "run_range"


@dataclass
class ScrapeBundle:
    """Scraped productions plus any concrete schedulable event series."""

    productions: List[TheaterProduction] = field(default_factory=list)
    series: List[EventSeries] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


DEFAULT_DURATION = timedelta(hours=1)
"""Fallback duration used when an event lacks an explicit end time."""
