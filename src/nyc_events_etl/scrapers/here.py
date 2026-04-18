from __future__ import annotations

"""Playwright scraper for HERE Arts Center."""

import logging
import re
from datetime import date, time

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import infer_end_time, infer_season_year, parse_clock_time
from .common import (
    body_lines,
    make_production,
    meta_content,
    open_page,
    same_domain_links,
    series_from_production,
)

THEATER_ID = "here"
THEATER_NAME = "HERE Arts Center"
SEED_URL = "https://here.org/shows/"
DEFAULT_VENUE = "HERE Arts Center"
DEFAULT_VENUE_ADDRESS = "145 Sixth Avenue, New York, NY 10013"
LOGGER = logging.getLogger("nyc_events_etl")

# Regex for annotations to strip: (PREVIEW), (OPENING), (MASK REQUIRED), etc.
_ANNOTATION_RE = re.compile(r"\s*\([^)]*\)\s*")

_MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

# Format A  – "Sunday, 4/5 at 4 pm"  (day-of-week, M/D, time)
_FORMAT_A_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r",?\s+(\d{1,2})/(\d{1,2})",
    re.I,
)

# Format B  – "Saturday June 13 @ 7 pm"  (day-of-week Month D, time)
#   Also matches "Wednesday, May 13 @ 8:30" (with comma after day-of-week)
_FORMAT_B_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r",?\s+(" + _MONTH_NAMES + r")"
    r"\s+(\d{1,2})",
    re.I,
)

# Format C  – "Thursday, April 30th, 8:30pm" (day-of-week, Month Dth, time)
#   Ordinal suffix (st, nd, rd, th) on the day number.
_FORMAT_C_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r",?\s+(" + _MONTH_NAMES + r")"
    r"\s+(\d{1,2})(?:st|nd|rd|th)",
    re.I,
)

# Format D  – "May 13th at 6:30PM" (Month Dth, time – no day-of-week)
_FORMAT_D_RE = re.compile(
    r"^(" + _MONTH_NAMES + r")"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"\s+(?:at|@)",
    re.I,
)

_MONTH_LOOKUP: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Time with am/pm: "7 pm", "8:30pm", "6:30PM", "2pm"
_TIME_AMPM_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[ap]m)", re.I)

# Bare time without am/pm: "@ 8:30", "@ 4"  (after stripping am/pm times)
_TIME_BARE_RE = re.compile(r"(?:@|at)\s+(\d{1,2}(?::\d{2})?)(?:\s|$|,)", re.I)


def _parse_time_flexible(text: str) -> time:
    """Parse a time string, defaulting bare numbers to PM for evening shows.

    Accepts ``"7 pm"``, ``"8:30pm"``, ``"8:30"`` (bare -> PM), ``"4"`` (bare -> PM).
    """
    cleaned = text.strip()
    # If it already has am/pm, use parse_clock_time directly
    if re.search(r"[ap]m", cleaned, re.I):
        return parse_clock_time(cleaned)
    # Bare time: assume PM (HERE shows are evening/matinee, never before noon)
    hour_min = cleaned.split(":")
    hour = int(hour_min[0])
    minute = int(hour_min[1]) if len(hour_min) > 1 else 0
    if hour < 12:
        hour += 12
    return time(hour, minute)


def _extract_times(text: str) -> list[time]:
    """Extract all times from a schedule line, handling both am/pm and bare times."""
    results: list[time] = []
    seen: set[time] = set()

    # First: find all am/pm times
    for t_str in _TIME_AMPM_RE.findall(text):
        try:
            t = parse_clock_time(t_str)
            if t not in seen:
                results.append(t)
                seen.add(t)
        except ValueError:
            pass

    # If we found am/pm times, return them (don't double-count with bare regex)
    if results:
        return results

    # Fallback: find bare times (like "@ 8:30", "@ 4")
    for t_str in _TIME_BARE_RE.findall(text):
        try:
            t = _parse_time_flexible(t_str)
            if t not in seen:
                results.append(t)
                seen.add(t)
        except ValueError:
            pass

    return results


def parse_here_schedule_lines(
    lines: list[str],
    *,
    reference_date: date | None = None,
) -> list[tuple[date, time]]:
    """Parse HERE's per-show schedule lines into ``(date, time)`` pairs.

    Handles four observed formats from HERE detail pages:

    * Format A: ``"Sunday, 4/5 at 4 pm"`` -- numeric month/day
    * Format B: ``"Saturday June 13 @ 7 pm"`` -- month name, day-of-week
    * Format C: ``"Thursday, April 30th, 8:30pm"`` -- month name with ordinal
    * Format D: ``"May 13th at 6:30PM"`` -- month name, no day-of-week

    Combined times like ``"4 pm & at 8:30 pm"`` or ``"2 pm and @ 7 pm"``
    produce multiple pairs for the same date.  Parenthetical annotations such
    as ``(PREVIEW)`` are stripped.  Times without am/pm default to PM.
    """
    reference = reference_date or date.today()
    results: list[tuple[date, time]] = []

    for raw_line in lines:
        # Strip annotations like (PREVIEW), (OPENING), (MASK REQUIRED), etc.
        cleaned = _ANNOTATION_RE.sub(" ", raw_line).strip()
        # Strip "+ Q&A" and similar suffixes
        cleaned = re.sub(r"\+\s*Q\s*&\s*A\b", "", cleaned).strip()
        # Remove trailing commas/punctuation
        cleaned = cleaned.rstrip(",;.")

        perf_date: date | None = None

        # Try Format A: "Day, M/D ..."
        m_a = _FORMAT_A_RE.search(cleaned)
        if m_a:
            month = int(m_a.group(1))
            day = int(m_a.group(2))
            year = infer_season_year(month, reference)
            perf_date = date(year, month, day)

        # Try Format C first (has ordinal suffix) before Format B (more general)
        if perf_date is None:
            m_c = _FORMAT_C_RE.search(cleaned)
            if m_c:
                month_name = m_c.group(1).lower()
                month = _MONTH_LOOKUP.get(month_name)
                if month is not None:
                    day = int(m_c.group(2))
                    year = infer_season_year(month, reference)
                    perf_date = date(year, month, day)

        # Try Format B: "Day Month D ..."
        if perf_date is None:
            m_b = _FORMAT_B_RE.search(cleaned)
            if m_b:
                month_name = m_b.group(1).lower()
                month = _MONTH_LOOKUP.get(month_name)
                if month is not None:
                    day = int(m_b.group(2))
                    year = infer_season_year(month, reference)
                    perf_date = date(year, month, day)

        # Try Format D: "Month Dth at/@ time" (no day-of-week)
        if perf_date is None:
            m_d = _FORMAT_D_RE.search(cleaned)
            if m_d:
                month_name = m_d.group(1).lower()
                month = _MONTH_LOOKUP.get(month_name)
                if month is not None:
                    day = int(m_d.group(2))
                    year = infer_season_year(month, reference)
                    perf_date = date(year, month, day)

        if perf_date is None:
            continue

        times = _extract_times(cleaned)
        for t in times:
            results.append((perf_date, t))

        if not times:
            LOGGER.warning("HERE: no time found in line: %s", raw_line)

    # Deduplicate while preserving order
    seen: set[tuple[date, time]] = set()
    deduped: list[tuple[date, time]] = []
    for item in results:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _is_schedule_line(line: str) -> bool:
    """Test whether a body text line looks like a performance schedule entry."""
    # Must have at least a time indicator
    has_time = bool(
        re.search(r"\d{1,2}(?::\d{2})?\s*[ap]m", line, re.I)
        or re.search(r"(?:@|at)\s+\d{1,2}(?::\d{2})?(?:\s|$|,)", line, re.I)
    )
    if not has_time:
        return False

    # Must have a date indicator: day-of-week or "M/D" or "Month D"
    has_date = bool(
        re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
            line,
            re.I,
        )
        or re.search(
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
            r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}",
            line,
            re.I,
        )
        or re.search(r"\d{1,2}/\d{1,2}", line)
    )
    return has_date


def _find_ticket_url(page) -> str:
    """Find a getcuebox.com ticket link on the page."""
    links = page.eval_on_selector_all(
        "a[href]",
        """els => els.map(a => ({href: a.href, text: (a.innerText || '').replace(/\\s+/g, ' ').trim()}))""",
    )
    for item in links:
        href = item["href"]
        text = item["text"]
        if "getcuebox.com" in href and re.search(r"ticket|buy", text, re.I):
            return href
    # Fallback: any getcuebox link with a show path
    for item in links:
        href = item["href"]
        if "getcuebox.com" in href and "/shows/" in href:
            return href
    return ""


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)

    # Collect detail page URLs from the listing page.
    raw_links = same_domain_links(listing_page, include="/shows/")
    detail_urls = [
        url for url in raw_links
        if "/shows/" in url
        and url.split("#")[0].rstrip("/") != SEED_URL.rstrip("/")
        and "/shows/type/" not in url
    ]
    # Deduplicate by base URL (ignoring fragments) while preserving order
    seen_urls: set[str] = set()
    unique_detail_urls: list[str] = []
    for url in detail_urls:
        normalized = url.split("#")[0].rstrip("/")
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique_detail_urls.append(url.split("#")[0])
    detail_urls = unique_detail_urls

    LOGGER.info("HERE detail URLs discovered: %d", len(detail_urls))
    listing_page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("HERE scraping detail page: %s", url)
        page = open_page(context, url)

        # Extract title from h1; fall back to page title if h1 is empty/missing.
        title = ""
        if page.locator("h1").count():
            title = page.locator("h1").first.inner_text().strip()
        if not title:
            title = page.title().replace(" - HERE", "").strip()

        # Extract description from og:description meta tag
        description = meta_content(page, 'meta[property="og:description"]')

        # Extract run range text (e.g. "April 5 - 19", "June 13 - July 11th",
        # "April 30th - May 3rd, 2026", "May 13th", "6/1/2026", "Ongoing").
        run_range_text = ""
        for line in body_lines(page):
            # Date range: "April 5 - 19", "June 5th - June 27th"
            if re.search(
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?\s*-",
                line,
                re.I,
            ):
                run_range_text = line
                break
            # Standalone "Ongoing"
            if re.fullmatch(r"Ongoing", line.strip(), re.I):
                run_range_text = line
                break
            # Numeric date: "6/1/2026"
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", line.strip()):
                run_range_text = line
                break
            # Single date: "May 13th" (only month + day, no other text)
            if re.fullmatch(
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?",
                line.strip(),
                re.I,
            ):
                run_range_text = line
                break

        # Find ticket URL
        ticket_url = _find_ticket_url(page)

        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=DEFAULT_VENUE,
            venue_address=DEFAULT_VENUE_ADDRESS,
            ticket_url=ticket_url,
            schedule_source_url=url,
            run_range_text=run_range_text,
        )
        bundle.productions.append(production)

        # Try to click "Tickets +" to expand the accordion (if it exists).
        tickets_toggle = page.locator("text=Tickets +").first
        if tickets_toggle.count():
            try:
                tickets_toggle.click(timeout=3000)
                page.wait_for_timeout(500)
            except Exception:
                pass  # Already expanded or not clickable

        # Extract schedule lines from body text
        all_lines = body_lines(page)
        schedule_lines = [line for line in all_lines if _is_schedule_line(line)]

        if schedule_lines:
            pairs = parse_here_schedule_lines(schedule_lines)
            LOGGER.info("HERE %s: extracted %d schedule instances", title, len(pairs))
            if pairs:
                grouped: dict[date, list[time]] = {}
                for perf_date, perf_time in pairs:
                    grouped.setdefault(perf_date, []).append(perf_time)
                for perf_date, perf_times in grouped.items():
                    perf_times = sorted(set(perf_times))
                    bundle.series.append(
                        series_from_production(
                            production,
                            dates=[perf_date],
                            start_times=perf_times,
                            end_time=infer_end_time(perf_times[0], duration_minutes=90),
                        )
                    )
                production.schedule_granularity = "instance"
                production.raw_schedule_text = " | ".join(schedule_lines[:50])
        else:
            LOGGER.info("HERE %s: no schedule lines found", title)

        page.close()

    return bundle
