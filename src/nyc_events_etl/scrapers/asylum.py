from __future__ import annotations

"""Playwright scraper for Asylum NYC via their Pixl Calendar / Tixr API."""

import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from .common import make_production, open_page, series_from_production

THEATER_ID = "asylum"
THEATER_NAME = "Asylum NYC"
SEED_URL = "https://calendar.asylumnyc.com/"
API_URL = "https://calendar.asylumnyc.com/api/events/asylum-nyc"
DEFAULT_VENUE = "Asylum NYC"
DEFAULT_VENUE_ADDRESS = "123 E 24th St, New York, NY 10010"

NY_TZ = ZoneInfo("America/New_York")
LOGGER = logging.getLogger("nyc_events_etl")


def strip_html(html_text: str) -> str:
    """Strip HTML tags from a string and return clean plain text."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def format_price(price_value) -> str:
    """Format a numeric price into a display string like '$30'."""
    if price_value is None:
        return ""
    try:
        amount = float(price_value)
    except (TypeError, ValueError):
        return ""
    if amount == 0:
        return "Free"
    if amount == int(amount):
        return f"${int(amount)}"
    return f"${amount:.2f}"


def parse_api_events(api_json: list[dict]) -> ScrapeBundle:
    """Parse the Asylum NYC API JSON response into a ScrapeBundle.

    Groups events by title so that recurring shows (e.g. "Chris Hall"
    appearing on many dates) become a single TheaterProduction with
    one EventSeries per distinct performance date.
    """
    bundle = ScrapeBundle()

    # Group events by title to create one production per unique show
    by_title: dict[str, list[dict]] = defaultdict(list)
    for event in api_json:
        title = (event.get("title") or "").strip()
        if not title:
            LOGGER.warning("Asylum: skipping event with no title: %s", event.get("id"))
            continue
        by_title[title].append(event)

    for title, events in by_title.items():
        # Use the first event for metadata (description, price, ticket URL, etc.)
        first = events[0]

        description = strip_html(first.get("description", ""))
        price = format_price(first.get("price"))
        ticket_url = first.get("ticketUrl", "")
        venue_name = first.get("venue") or DEFAULT_VENUE
        source_url = ticket_url or SEED_URL

        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            price=price,
            source_url=source_url,
            venue_name=venue_name,
            venue_address=DEFAULT_VENUE_ADDRESS,
            ticket_url=ticket_url,
            schedule_source_url=SEED_URL,
            schedule_granularity="instance",
        )
        bundle.productions.append(production)

        # Collect all (date, start_time, end_time) instances for this production
        for event in events:
            start_str = event.get("start", "")
            end_str = event.get("end", "")

            if not start_str:
                LOGGER.warning("Asylum: no start time for '%s' event %s", title, event.get("id"))
                continue

            try:
                start_utc = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start_local = start_utc.astimezone(NY_TZ)
            except (ValueError, TypeError) as exc:
                LOGGER.warning("Asylum: invalid start time '%s' for '%s': %s", start_str, title, exc)
                continue

            end_time_val = None
            if end_str:
                try:
                    end_utc = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    end_local = end_utc.astimezone(NY_TZ)
                    end_time_val = end_local.time().replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass

            perf_date = start_local.date()
            start_time_val = start_local.time().replace(tzinfo=None)

            # Use per-event ticket URL if available, else fall back to production-level
            event_ticket_url = event.get("ticketUrl", "") or ticket_url

            bundle.series.append(
                series_from_production(
                    production,
                    dates=[perf_date],
                    start_times=[start_time_val],
                    end_time=end_time_val,
                )
            )
            # Override ticket_url per series if different
            if event_ticket_url and event_ticket_url != ticket_url:
                bundle.series[-1].ticket_url = event_ticket_url

    LOGGER.info("Asylum: parsed %d productions, %d series from API", len(bundle.productions), len(bundle.series))
    return bundle


def extract_events_list(api_data) -> list[dict] | None:
    """Extract the events list from the API response.

    The API returns either:
    - A dict with an "events" key containing the list
    - A plain list of event dicts
    Returns None if the format is unrecognized.
    """
    if isinstance(api_data, list):
        return api_data
    if isinstance(api_data, dict):
        events = api_data.get("events")
        if isinstance(events, list):
            return events
    return None


def scrape(context: BrowserContext) -> ScrapeBundle:
    """Scrape Asylum NYC events via the calendar API."""

    # Open the page to establish a browser session (cookies, etc.)
    page = open_page(context, SEED_URL)

    # Navigate to the API endpoint to get JSON data
    LOGGER.info("Asylum: fetching API at %s", API_URL)
    response = page.goto(API_URL, wait_until="domcontentloaded", timeout=30_000)

    if response is None or not response.ok:
        status = response.status if response else "no response"
        LOGGER.error("Asylum: API request failed with status %s", status)
        page.close()
        return ScrapeBundle(warnings=[f"API request failed: {status}"])

    # Parse the JSON response from the page body
    try:
        raw_text = page.locator("body").inner_text()
        api_data = json.loads(raw_text)
    except (json.JSONDecodeError, Exception) as exc:
        LOGGER.error("Asylum: failed to parse API JSON: %s", exc)
        page.close()
        return ScrapeBundle(warnings=[f"Failed to parse API JSON: {exc}"])

    page.close()

    # API returns {"events": [...], "total": N, ...} - extract the events list
    events_list = extract_events_list(api_data)
    if events_list is None:
        LOGGER.warning("Asylum: could not extract events from API response (type: %s)", type(api_data).__name__)
        return ScrapeBundle(warnings=["API returned unexpected format"])

    LOGGER.info("Asylum: API returned %d events", len(events_list))
    return parse_api_events(events_list)
