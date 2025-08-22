from __future__ import annotations

"""Utilities for parsing fuzzy date and time expressions without external deps."""

from datetime import date, datetime, time
import calendar
import re
from typing import List, Tuple, Optional

WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

ORDINAL_MAP = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}

MONTH_ABBR = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}


def _parse_time(text: str) -> time:
    text = text.strip()
    fmt = "%I:%M %p" if ":" in text else "%I %p"
    return datetime.strptime(text, fmt).time()


def parse_dates(phrase: str, year: int, default_month: Optional[int] = None) -> List[date]:
    """Parse human-readable date phrase into ``date`` objects.

    Parameters
    ----------
    phrase:
        Text describing one or more dates.
    year:
        Calendar year the dates belong to.
    default_month:
        Month used when ``phrase`` does not explicitly contain one (e.g.
        "every Thursday").
    """

    phrase = phrase.strip().lower()

    # recurring: "every thursday"
    m = re.fullmatch(r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", phrase)
    if m:
        month = default_month or 1
        weekday = WEEKDAY_MAP[m.group(1)]
        first_weekday, days_in_month = calendar.monthrange(year, month)
        offset = (weekday - first_weekday) % 7
        return [date(year, month, d) for d in range(1 + offset, days_in_month + 1, 7)]

    # ordinal weekday: "first sunday of every month"
    m = re.fullmatch(r"(first|second|third|fourth|fifth)\s+(\w+)\s+of\s+every\s+month", phrase)
    if m:
        ord_ = ORDINAL_MAP[m.group(1)]
        weekday = WEEKDAY_MAP[m.group(2)]
        month = default_month or 1
        first_weekday, _ = calendar.monthrange(year, month)
        day = 1 + (weekday - first_weekday) % 7 + (ord_ - 1) * 7
        return [date(year, month, day)]

    if "&" in phrase or "," in phrase:
        parts = re.split(r"[&,]", phrase)
        month = MONTH_ABBR[parts[0].strip().split()[0][:3]]
        dates: List[date] = []
        for part in parts:
            tokens = part.strip().split()
            if len(tokens) == 1:
                day = int(tokens[0])
            else:
                month = MONTH_ABBR[tokens[0][:3]]
                day = int(tokens[1])
            dates.append(date(year, month, day))
        return dates

    m = re.fullmatch(r"(\w+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})", phrase)
    if m:
        month = MONTH_ABBR[m.group(1)[:3]]
        start_day, end_day = int(m.group(2)), int(m.group(3))
        return [date(year, month, d) for d in range(start_day, end_day + 1)]

    m = re.fullmatch(r"through\s+(\w+)\s+(\d{1,2})", phrase)
    if m:
        month = MONTH_ABBR[m.group(1)[:3]]
        end_day = int(m.group(2))
        return [date(year, month, d) for d in range(1, end_day + 1)]

    tokens = phrase.split()
    month = MONTH_ABBR[tokens[0][:3]]
    day = int(tokens[1])
    return [date(year, month, day)]


def parse_times(phrase: str) -> Tuple[List[time], Optional[time]]:
    """Parse a time expression into start times and optional end time."""

    phrase = phrase.strip().lower()
    phrase = re.sub(r"\(.*?doors.*?\)", "", phrase)

    if "-" in phrase or "–" in phrase:
        start_part, end_part = re.split(r"[-–]", phrase)
        suffix = "pm" if "pm" in phrase else "am"
        start_suffix = "am" if "am" in start_part else ("pm" if "pm" in start_part else suffix)
        end_suffix = "am" if "am" in end_part else ("pm" if "pm" in end_part else suffix)
        start_text = start_part.strip()
        if not any(s in start_text for s in ["am", "pm"]):
            start_text += " " + start_suffix
        end_text = end_part.strip()
        if not any(s in end_text for s in ["am", "pm"]):
            end_text += " " + end_suffix
        start = _parse_time(start_text)
        end = _parse_time(end_text)
        return [start], end

    if "&" in phrase:
        base = "pm" if "pm" in phrase else "am"
        parts = phrase.replace(base, "").split("&")
        times = [_parse_time(p.strip() + " " + base) for p in parts]
        return times, None

    suffix = "pm" if "pm" in phrase else "am"
    cleaned = phrase.replace("pm", "").replace("am", "").strip() + " " + suffix
    return [_parse_time(cleaned)], None
