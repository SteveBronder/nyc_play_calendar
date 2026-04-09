from __future__ import annotations

"""Helpers for converting ticket/calendar text into normalized schedules."""

from datetime import date, datetime, time, timedelta
import calendar
import re
from typing import Iterable, List, Sequence

from .date_parsing import MONTH_ABBR

WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

MONTH_PATTERN = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"


def parse_month_day_year(text: str, default_year: int | None = None) -> date:
    """Parse text like ``May 12, 2026`` or ``Feb 18 2026`` into ``date``."""

    cleaned = re.sub(r"[^A-Za-z0-9, ]+", " ", text).strip()
    m = re.search(rf"{MONTH_PATTERN}\s+(\d{{1,2}})(?:,\s*|\s+)(\d{{4}})?", cleaned, re.I)
    if not m:
        raise ValueError(f"Unsupported month/day/year text: {text!r}")
    month = MONTH_ABBR[m.group(1)[:3].lower()]
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else default_year
    if year is None:
        raise ValueError(f"Year required for {text!r}")
    return date(year, month, day)


def parse_month_day_range_year(text: str, default_year: int | None = None) -> list[date]:
    """Parse ``May 4-5, 2026`` or a single date into one or more dates."""

    cleaned = re.sub(r"[^A-Za-z0-9, -]+", " ", text).strip()
    rng = re.search(rf"{MONTH_PATTERN}\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})(?:,\s*|\s+)(\d{{4}})?", cleaned, re.I)
    if rng:
        month = MONTH_ABBR[rng.group(1)[:3].lower()]
        start_day = int(rng.group(2))
        end_day = int(rng.group(3))
        year = int(rng.group(4)) if rng.group(4) else default_year
        if year is None:
            raise ValueError(f"Year required for {text!r}")
        return [date(year, month, day) for day in range(start_day, end_day + 1)]
    return [parse_month_day_year(text, default_year=default_year)]


def parse_clock_time(text: str) -> time:
    """Parse times like ``7 PM`` or ``7:00pm``."""

    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    cleaned = cleaned.replace(".", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", cleaned)
    if not m:
        raise ValueError(f"Unsupported time text: {text!r}")
    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    suffix = m.group(3)
    if hour == 12:
        hour = 0
    if suffix == "pm":
        hour += 12
    return time(hour, minute)


def infer_season_year(month: int, reference_date: date | None = None) -> int:
    """Infer a season year for month/day text that omits the year."""

    reference = reference_date or date.today()
    if reference.month <= 6 and month >= 8:
        return reference.year - 1
    if reference.month >= 8 and month <= 6:
        return reference.year + 1
    return reference.year


def parse_vineyard_schedule_lines(lines: Sequence[str]) -> list[tuple[date, time]]:
    """Parse Vineyard's box-office list view into concrete instances."""

    matches: list[tuple[date, time]] = []
    pattern = re.compile(rf"({MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}})\s+\|\s+(\d{{1,2}}:\d{{2}}\s+[AP]M)", re.I)
    for line in lines:
        m = pattern.search(line)
        if not m:
            continue
        matches.append((parse_month_day_year(m.group(1)), parse_clock_time(m.group(3))))
    return matches


def parse_nytw_ticket_calendar(lines: Sequence[str]) -> list[tuple[date, time]]:
    """Parse NYTW's month/day/time ticket calendar text."""

    results: list[tuple[date, time]] = []
    month = year = current_day = None
    active_month = None
    active_year = None
    previous_day = None
    for raw in lines:
        line = raw.strip()
        header = re.fullmatch(rf"{MONTH_PATTERN}\s+(\d{{4}})", line, re.I)
        if header:
            month = MONTH_ABBR[header.group(1)[:3].lower()]
            year = int(header.group(2))
            current_day = None
            active_month = month
            active_year = year
            previous_day = None
            continue
        if re.fullmatch(r"\d{1,2}", line):
            current_day = int(line)
            continue
        if month is None or year is None or current_day is None:
            continue
        time_match = re.match(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", line, re.I)
        if not time_match:
            continue
        if active_month is None or active_year is None:
            active_month = month
            active_year = year
        if previous_day is not None and current_day < previous_day:
            active_month += 1
            if active_month > 12:
                active_month = 1
                active_year += 1
        max_day = calendar.monthrange(active_year, active_month)[1]
        if current_day > max_day:
            active_month += 1
            if active_month > 12:
                active_month = 1
                active_year += 1
        results.append((date(active_year, active_month, current_day), parse_clock_time(time_match.group(1))))
        previous_day = current_day
    return results


def parse_performance_space_schedule_lines(
    lines: Sequence[str],
    *,
    reference_date: date | None = None,
) -> list[tuple[date, time]]:
    """Parse explicit date/time lines from Performance Space show pages."""

    reference = reference_date or date.today()
    results: list[tuple[date, time]] = []
    active_date: date | None = None
    inline_pattern = re.compile(
        rf"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(\d{{4}}))?\s*\|\s*"
        rf"(\d{{1,2}}(?::\d{{2}})?\s*[APap][Mm])",
        re.I,
    )
    header_pattern = re.compile(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(\d{{4}}))?"
        rf"(?:\s*\(click to see schedule\))?:?$",
        re.I,
    )
    time_pattern = re.compile(r"^\d{1,2}(?::\d{2})?\s*[APap][Mm]$", re.I)

    for raw_line in lines:
        line = raw_line.strip()
        inline = inline_pattern.search(line)
        if inline:
            month = MONTH_ABBR[inline.group(1)[:3].lower()]
            year = int(inline.group(4)) if inline.group(4) else infer_season_year(month, reference)
            results.append((date(year, month, int(inline.group(3))), parse_clock_time(inline.group(5))))
            active_date = None
            continue
        header = header_pattern.match(line)
        if header:
            month = MONTH_ABBR[header.group(1)[:3].lower()]
            year = int(header.group(4)) if header.group(4) else infer_season_year(month, reference)
            active_date = date(year, month, int(header.group(3)))
            continue
        if active_date and time_pattern.match(line):
            results.append((active_date, parse_clock_time(line)))

    deduped: list[tuple[date, time]] = []
    seen: set[tuple[date, time]] = set()
    for item in results:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def parse_date_range(text: str, default_year: int) -> tuple[date, date]:
    """Parse common run-range strings into start/end dates."""

    cleaned = re.sub(r"\s+", " ", text.replace("—", "-").replace("–", "-")).strip()
    m = re.search(
        rf"{MONTH_PATTERN}\s+(\d{{1,2}})(?:,\s*|\s+)?(\d{{4}})?\s*-\s*{MONTH_PATTERN}\s+(\d{{1,2}})(?:,\s*|\s+)?(\d{{4}})?",
        cleaned,
        re.I,
    )
    if m:
        start_month = MONTH_ABBR[m.group(1)[:3].lower()]
        start_day = int(m.group(2))
        start_year = int(m.group(3)) if m.group(3) else default_year
        end_month = MONTH_ABBR[m.group(4)[:3].lower()]
        end_day = int(m.group(5))
        end_year = int(m.group(6)) if m.group(6) else start_year + (1 if end_month < start_month else 0)
        return date(start_year, start_month, start_day), date(end_year, end_month, end_day)

    single = re.search(rf"{MONTH_PATTERN}\s+(\d{{1,2}})(?:,\s*|\s+)?(\d{{4}})?", cleaned, re.I)
    if not single:
        raise ValueError(f"Unsupported date range: {text!r}")
    month = MONTH_ABBR[single.group(1)[:3].lower()]
    day = int(single.group(2))
    year = int(single.group(3)) if single.group(3) else default_year
    one = date(year, month, day)
    return one, one


def expand_weekly_schedule(range_text: str, recurrence_text: str, default_year: int) -> list[tuple[date, time]]:
    """Expand text like ``APR 2 - APR 19; THU, FRI at 8 PM, SUN at 3 PM``."""

    start, end = parse_date_range(range_text, default_year)
    results: list[tuple[date, time]] = []
    normalized = recurrence_text.replace("&", ",")
    for part in re.findall(r"([A-Z ,]+?\s+at\s+\d{1,2}(?::\d{2})?\s*[AP]M)", normalized, re.I):
        m = re.match(r"([A-Z ,]+)\s+at\s+(\d{1,2}(?::\d{2})?\s*[AP]M)", part.strip(), re.I)
        if not m:
            continue
        weekdays = [WEEKDAY_MAP[token.strip().lower()] for token in m.group(1).split(",") if token.strip()]
        perf_time = parse_clock_time(m.group(2))
        cursor = start
        while cursor <= end:
            if cursor.weekday() in weekdays:
                results.append((cursor, perf_time))
            cursor += timedelta(days=1)
    return sorted(results)


def extract_range_and_recurrence(text: str) -> tuple[str, str] | None:
    """Split schedule text into a run range and weekday/time recurrence."""

    normalized = re.sub(r"\s+", " ", text).strip()
    if ";" in normalized:
        left, right = normalized.split(";", 1)
        return left.strip(), right.strip()
    m = re.match(
        rf"(({MONTH_PATTERN}\s+\d{{1,2}}\s*-\s*{MONTH_PATTERN}\s+\d{{1,2}})|({MONTH_PATTERN}\s+\d{{1,2}}\s*-\s*\d{{1,2}})|([A-Z]{{3}}\s+\d{{1,2}}\s*-\s*[A-Z]{{3}}\s+\d{{1,2}}))\s*,\s*(.+)$",
        normalized,
        re.I,
    )
    if not m:
        return None
    return m.group(1).strip(), m.group(m.lastindex).strip()


def collect_body_lines(text: str) -> list[str]:
    """Normalize page text into non-empty lines."""

    return [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]


def format_run_range(start: date, end: date) -> str:
    """Return a compact human-readable run range."""

    if start == end:
        return start.strftime("%b %-d, %Y")
    if start.year == end.year:
        return f"{start.strftime('%b %-d')} - {end.strftime('%b %-d, %Y')}"
    return f"{start.strftime('%b %-d, %Y')} - {end.strftime('%b %-d, %Y')}"


def infer_end_time(start_time: time, duration_minutes: int = 120) -> time:
    """Create a simple fallback end time for explicit instances."""

    dt = datetime.combine(date(2000, 1, 1), start_time) + timedelta(minutes=duration_minutes)
    return dt.time()
