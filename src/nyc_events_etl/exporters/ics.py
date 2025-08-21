"""ICS file export functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models import EventInstance


def export_ics(events: Iterable[EventInstance], path: str | Path) -> None:
    """Write events to an ICS file.

    The heavy icalendar dependency is imported lazily so that tests and tools
    that do not require ICS export can run without it.
    """

    from icalendar import Calendar, Event  # type: ignore

    cal = Calendar()
    cal.add("prodid", "-//NYC Events ETL//")
    cal.add("version", "2.0")

    for ev in events:
        e = Event()
        e.add("uid", ev.uid)
        e.add("summary", ev.title)
        e.add("dtstart", ev.start)
        e.add("dtend", ev.end)
        if ev.description:
            e.add("description", ev.description)
        if ev.venue_name:
            loc = ev.venue_name
            if ev.venue_address:
                loc += f" - {ev.venue_address}"
            e.add("location", loc)
        cal.add_component(e)

    Path(path).write_bytes(cal.to_ical())

