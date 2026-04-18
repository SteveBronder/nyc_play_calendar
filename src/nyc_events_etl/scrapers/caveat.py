from __future__ import annotations

"""Playwright scraper for Caveat NYC events via their JSON API."""

import json
import logging
from datetime import date, time

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import infer_end_time, parse_clock_time
from .common import make_production, open_page, series_from_production

THEATER_ID = "caveat"
THEATER_NAME = "Caveat"
SEED_URL = "https://www.caveat.nyc/events"
API_URL = "https://www.caveat.nyc/api/events/listings"
DEFAULT_VENUE = "Caveat"
DEFAULT_VENUE_ADDRESS = "21 A Clinton Street, New York, NY 10002"

LOGGER = logging.getLogger("nyc_events_etl")


def _build_price_text(fields: dict) -> str:
    """Build a human-readable price string from the ticket pricing fields."""
    parts: list[str] = []
    advance = fields.get("Tickets advance")
    door = fields.get("Tickets door")
    livestream = fields.get("Tickets Livestream")
    premium = fields.get("Tickets Premium")

    if advance is not None:
        parts.append(f"${advance:.0f} advance")
    if door is not None and door != advance:
        parts.append(f"${door:.0f} door")
    if premium is not None and premium != advance:
        parts.append(f"${premium:.0f} premium")
    if livestream is not None:
        parts.append(f"${livestream:.0f} livestream")
    return ", ".join(parts)


def _parse_time(text: str | None) -> time | None:
    """Parse a time string like '7:00 PM', returning None on failure."""
    if not text:
        return None
    try:
        return parse_clock_time(text)
    except ValueError:
        LOGGER.warning("Caveat: could not parse time %r", text)
        return None


def _parse_date(text: str | None) -> date | None:
    """Parse a date string like '2026-04-18', returning None on failure."""
    if not text:
        return None
    try:
        parts = text.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        LOGGER.warning("Caveat: could not parse date %r", text)
        return None


def parse_api_response(raw_json: str) -> list[dict]:
    """Parse the Caveat API JSON into a list of normalized event dicts.

    This is broken out as a standalone function so it can be unit-tested
    without a browser.
    """
    data = json.loads(raw_json)
    records = data.get("records", [])
    events: list[dict] = []

    for record in records:
        fields = record.get("fields", {})
        title = fields.get("Event", "").strip()
        if not title:
            continue

        event_date = _parse_date(fields.get("datestring"))
        if event_date is None:
            LOGGER.warning("Caveat: skipping event %r with no date", title)
            continue

        start_time = _parse_time(fields.get("Event start TIME ONLY"))
        if start_time is None:
            LOGGER.warning("Caveat: skipping event %r with no start time", title)
            continue

        description = (fields.get("description") or "").strip()
        short_desc = (fields.get("Short description") or "").strip()
        # Use full description if available, otherwise short description
        if not description:
            description = short_desc

        ticket_url = fields.get("Ticket URL", "")
        slug = fields.get("slug", "")
        price_text = _build_price_text(fields)
        sold_out = bool(fields.get("Sold out"))

        if sold_out and price_text:
            price_text = f"SOLD OUT ({price_text})"
        elif sold_out:
            price_text = "SOLD OUT"

        events.append({
            "title": title,
            "date": event_date,
            "start_time": start_time,
            "description": description,
            "ticket_url": ticket_url,
            "price": price_text,
            "slug": slug,
        })

    return events


def scrape(context: BrowserContext) -> ScrapeBundle:
    """Scrape Caveat NYC events from their JSON API."""
    bundle = ScrapeBundle()

    # Open the main events page to establish the browser session
    page = open_page(context, SEED_URL)

    # Fetch event data from the API via page.evaluate
    LOGGER.info("Caveat: fetching API data from %s", API_URL)
    try:
        raw_json = page.evaluate(
            """async (apiUrl) => {
                const resp = await fetch(apiUrl);
                return await resp.text();
            }""",
            API_URL,
        )
    except Exception as exc:
        LOGGER.exception("Caveat: failed to fetch API: %s", exc)
        page.close()
        return ScrapeBundle(warnings=[f"Failed to fetch API: {exc}"])

    page.close()

    if not raw_json or raw_json.startswith("<!"):
        LOGGER.warning("Caveat: API returned non-JSON response")
        return ScrapeBundle(warnings=["API returned non-JSON response"])

    try:
        events = parse_api_response(raw_json)
    except (json.JSONDecodeError, KeyError) as exc:
        LOGGER.exception("Caveat: failed to parse API response: %s", exc)
        return ScrapeBundle(warnings=[f"Failed to parse API: {exc}"])

    LOGGER.info("Caveat: parsed %d events from API", len(events))

    for event in events:
        source_url = event["ticket_url"] or f"https://www.caveat.nyc/event/{event['slug']}"

        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=event["title"],
            description=event["description"],
            price=event["price"],
            source_url=source_url,
            venue_name=DEFAULT_VENUE,
            venue_address=DEFAULT_VENUE_ADDRESS,
            ticket_url=event["ticket_url"],
            schedule_source_url=SEED_URL,
            schedule_granularity="instance",
        )
        bundle.productions.append(production)

        end_time = infer_end_time(event["start_time"], duration_minutes=90)
        series = series_from_production(
            production,
            dates=[event["date"]],
            start_times=[event["start_time"]],
            end_time=end_time,
        )
        bundle.series.append(series)

    LOGGER.info(
        "Caveat: %d productions, %d series",
        len(bundle.productions),
        len(bundle.series),
    )
    return bundle
