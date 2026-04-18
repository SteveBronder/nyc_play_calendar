from __future__ import annotations

"""Playwright scraper for The Public Theater (including Joe's Pub)."""

import logging
import re
from datetime import date, time

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import format_run_range, infer_end_time, parse_clock_time
from .common import (
    body_lines,
    make_production,
    meta_content,
    open_page,
    series_from_production,
)

THEATER_ID = "public_theater"
THEATER_NAME = "The Public Theater"
SEED_URL = "https://publictheater.org/calendar/"
DEFAULT_VENUE = "The Public Theater"
DEFAULT_VENUE_ADDRESS = "425 Lafayette Street, New York, NY 10003"
LOGGER = logging.getLogger("nyc_events_etl")

MONTH_ABBR = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Pattern to parse "Fri, April 17 | 7:00PM"
DATE_TIME_PATTERN = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,\s+"
    r"(\w+)\s+(\d{1,2})\s*\|\s*"
    r"(\d{1,2}:\d{2}\s*[APap][Mm])",
)


def _parse_calendar_datetime(text: str, year: int) -> tuple[date, time] | None:
    """Parse a calendar entry like ``Fri, April 17 | 7:00PM``."""
    m = DATE_TIME_PATTERN.search(text)
    if not m:
        return None
    month_name = m.group(1).lower()
    month = MONTH_ABBR.get(month_name)
    if month is None:
        return None
    day = int(m.group(2))
    perf_time = parse_clock_time(m.group(3))
    return date(year, month, day), perf_time


def _extract_events_from_page(page) -> list[dict]:
    """Extract all event entries from the currently loaded list view."""
    return page.evaluate("""() => {
        const results = [];
        const headings = document.querySelectorAll('h5');
        for (const h5 of headings) {
            const container = h5.closest('div[class]') || h5.parentElement?.parentElement;
            if (!container) continue;
            const link = container.querySelector('a[href]');
            const ps = container.querySelectorAll('p');
            const dateTime = ps.length > 0 ? ps[0].innerText.trim() : '';
            const venue = ps.length >= 2 ? ps[ps.length - 1].innerText.trim() : '';
            if (dateTime && h5.innerText.trim()) {
                results.push({
                    dateTime: dateTime,
                    title: h5.innerText.trim(),
                    url: link ? link.href : '',
                    venue: venue,
                });
            }
        }
        return results;
    }""")


def _click_load_more(page) -> bool:
    """Click the 'Load More...' button if present. Returns True if clicked."""
    btn = page.locator("button:has-text('Load More')")
    if btn.count() > 0 and btn.is_visible():
        btn.click()
        page.wait_for_timeout(2_000)
        return True
    return False


def _scrape_detail_page(context: BrowserContext, url: str) -> dict:
    """Visit a production detail page and extract description/metadata.

    Returns a dict with keys: description, run_range_text, price, ticket_url.
    Waits extra time to allow Cloudflare challenge pages to resolve.
    """
    result = {"description": "", "run_range_text": "", "price": "", "ticket_url": ""}
    try:
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        # Wait longer to allow Cloudflare challenges to resolve
        page.wait_for_timeout(5_000)

        # Check if we got a real page (not a Cloudflare challenge)
        title = page.title()
        if "just a moment" in title.lower():
            LOGGER.info("Public Theater Cloudflare challenge on %s, skipping detail", url)
            page.close()
            return result

        result["description"] = meta_content(page, 'meta[property="og:description"]')

        for line in body_lines(page):
            if not result["run_range_text"] and re.search(
                r"\w+ \d{1,2},?\s+\d{4}\s*-\s*\w+ \d{1,2},?\s+\d{4}", line
            ):
                result["run_range_text"] = line
            if not result["price"] and re.search(r"(?:Tickets|tickets)\s+(?:are\s+)?\$", line):
                result["price"] = line

        ticket_links = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(a => ({href: a.href, text: (a.innerText || '').trim()}))""",
        )
        for item in ticket_links:
            if re.search(r"ticket|buy", item["text"], re.I) and "http" in item["href"]:
                result["ticket_url"] = item["href"]
                break

        page.close()
    except Exception as exc:
        LOGGER.warning("Public Theater failed to load detail page %s: %s", url, exc)
    return result


def scrape(context: BrowserContext) -> ScrapeBundle:
    page = open_page(context, SEED_URL)

    # Switch to List view for cleaner parsing
    list_btn = page.locator("button:has-text('List')")
    if list_btn.count() > 0:
        list_btn.click()
        page.wait_for_timeout(3_000)

    # Collect the available months from the dropdown
    month_options = page.locator("select").first.locator("option").all_inner_texts()
    LOGGER.info("Public Theater months available: %s", month_options)

    # Build a map of month_name -> year from the dropdown labels
    month_year_map: dict[str, int] = {}
    for label in month_options:
        parts = label.strip().split()
        if len(parts) == 2:
            month_year_map[parts[0].lower()] = int(parts[1])

    # Collect all raw events across all months
    raw_events: list[dict] = []

    for month_label in month_options:
        LOGGER.info("Public Theater selecting month: %s", month_label)
        page.locator("select").first.select_option(label=month_label)
        page.wait_for_timeout(3_000)

        # Wait for events to load
        try:
            searching = page.locator("text=Searching for events")
            if searching.count() > 0 and searching.is_visible():
                searching.wait_for(state="hidden", timeout=10_000)
        except Exception:
            pass
        page.wait_for_timeout(2_000)

        # Click "Load More" until all events for this month are visible
        while _click_load_more(page):
            LOGGER.info("Public Theater clicked Load More for %s", month_label)

        # Extract events
        events = _extract_events_from_page(page)
        LOGGER.info("Public Theater %s: found %d events", month_label, len(events))
        raw_events.extend(events)

    page.close()

    # Group raw events by production URL
    production_events: dict[str, list[dict]] = {}
    for evt in raw_events:
        url = evt.get("url", "")
        if not url:
            continue
        production_events.setdefault(url, []).append(evt)

    LOGGER.info("Public Theater found %d unique productions", len(production_events))

    # Identify mainstage productions (multi-show runs) for detail page visits
    mainstage_urls = {
        url for url, evts in production_events.items()
        if len(evts) >= 5 and "/productions/" in url
    }

    bundle = ScrapeBundle()

    for prod_url, events in production_events.items():
        first = events[0]
        title = first["title"]
        venue_name = first.get("venue", "") or DEFAULT_VENUE

        # Pre-parse all dates so we can compute run range
        parsed_pairs: list[tuple[date, time]] = []
        for evt in events:
            dt_text = evt["dateTime"]
            month_match = re.search(
                r"(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)",
                dt_text, re.I,
            )
            if not month_match:
                continue
            year = month_year_map.get(month_match.group(1).lower())
            if year is None:
                continue
            result = _parse_calendar_datetime(dt_text, year)
            if result:
                parsed_pairs.append(result)

        # Compute run range from parsed dates
        run_range_text = ""
        if parsed_pairs:
            all_dates = sorted(set(d for d, _ in parsed_pairs))
            run_range_text = format_run_range(all_dates[0], all_dates[-1])

        # Only visit detail pages for mainstage productions to get descriptions
        description = ""
        price = ""
        ticket_url = ""
        if prod_url in mainstage_urls:
            detail = _scrape_detail_page(context, prod_url)
            description = detail["description"]
            price = detail["price"]
            ticket_url = detail["ticket_url"]
            if detail["run_range_text"]:
                run_range_text = detail["run_range_text"]

        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=prod_url,
            venue_name=venue_name,
            venue_address=DEFAULT_VENUE_ADDRESS,
            ticket_url=ticket_url or prod_url,
            schedule_source_url=SEED_URL,
            run_range_text=run_range_text,
            price=price,
        )
        bundle.productions.append(production)

        # Add event instances
        for perf_date, perf_time in parsed_pairs:
            bundle.series.append(
                series_from_production(
                    production,
                    dates=[perf_date],
                    start_times=[perf_time],
                    end_time=infer_end_time(perf_time, duration_minutes=120),
                )
            )

        if parsed_pairs:
            bundle.productions[-1].schedule_granularity = "instance"

        LOGGER.info(
            "Public Theater %s: %d instances from %d events",
            title, len(parsed_pairs), len(events),
        )

    return bundle
