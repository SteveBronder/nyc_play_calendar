from __future__ import annotations

"""ICS (iCalendar) file generation without external dependencies."""

from typing import Iterable

from .models import EventInstance


def _format_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


def _format_date(dt):
    return dt.strftime("%Y%m%d")


def events_to_ics(events: Iterable[EventInstance], calendar_name: str = "NYC Events") -> bytes:
    """Create an ICS representation of ``events``.

    The implementation is intentionally minimal but produces valid VCALENDAR
    output for the features used in the tests.
    """

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NYC Events ETL//",
        f"X-WR-CALNAME:{calendar_name}",
    ]
    for event in events:
        if event.all_day:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.uid}",
                    f"SUMMARY:{event.title}",
                    f"DESCRIPTION:{event.description}\nPrice: {event.price}",
                    f"LOCATION:{event.venue_name} – {event.venue_address}",
                    f"DTSTART;VALUE=DATE:{_format_date(event.start)}",
                    f"DTEND;VALUE=DATE:{_format_date(event.end)}",
                    "END:VEVENT",
                ]
            )
        else:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.uid}",
                    f"SUMMARY:{event.title}",
                    f"DESCRIPTION:{event.description}\nPrice: {event.price}",
                    f"LOCATION:{event.venue_name} – {event.venue_address}",
                    (
                        f"DTSTART;TZID={event.start.tzinfo.key}:{_format_dt(event.start)}"
                        if event.start.tzinfo
                        else f"DTSTART:{_format_dt(event.start)}"
                    ),
                    (
                        f"DTEND;TZID={event.end.tzinfo.key}:{_format_dt(event.end)}"
                        if event.end.tzinfo
                        else f"DTEND:{_format_dt(event.end)}"
                    ),
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")
