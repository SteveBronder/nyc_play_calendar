from __future__ import annotations

"""Playwright scraper for Astor Place Theatre."""

import logging

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import infer_end_time
from .common import (
    json_ld_objects,
    make_production,
    open_page,
    parse_ticketmaster_events,
    series_from_production,
)

THEATER_ID = "astor_place"
THEATER_NAME = "Astor Place Theatre"
SEED_URL = "https://astorplacetheatre.com/productions/"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    page = open_page(context, SEED_URL)
    bundle = ScrapeBundle()

    for obj in json_ld_objects(page):
        if obj.get("@type") != "TheaterEvent":
            continue
        offers = obj.get("offers") or {}
        location = obj.get("location") or {}
        address = location.get("address") or {}
        venue_address = ", ".join(
            part
            for part in (
                address.get("streetAddress", ""),
                address.get("addressLocality", ""),
                address.get("postalCode", ""),
                address.get("addressCountry", ""),
            )
            if part
        )
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=obj.get("name", ""),
            description=obj.get("description", ""),
            source_url=SEED_URL,
            venue_name=location.get("name", THEATER_NAME),
            venue_address=venue_address,
            price=str(offers.get("lowPrice", "")),
            ticket_url=offers.get("url", ""),
            schedule_source_url=offers.get("url", "") or SEED_URL,
            run_range_text=obj.get("startDate", ""),
        )
        bundle.productions.append(production)
        LOGGER.info("Astor Place captured production from JSON-LD: %s", production.title)
        if not production.ticket_url:
            continue
        ticket_page = open_page(context, production.ticket_url)
        ticket_events = parse_ticketmaster_events(ticket_page)
        LOGGER.info("Astor Place %s extracted %d Ticketmaster instances", production.title, len(ticket_events))
        grouped: dict = {}
        for event in ticket_events:
            grouped.setdefault(event["date"], []).append(event["time"])
            if not production.venue_address and event["venue_address"]:
                production.venue_address = event["venue_address"]
        for perf_date, perf_times in sorted(grouped.items()):
            perf_times = sorted(set(perf_times))
            bundle.series.append(
                series_from_production(
                    production,
                    dates=[perf_date],
                    start_times=perf_times,
                    end_time=infer_end_time(perf_times[0], duration_minutes=110),
                )
            )
        if grouped:
            bundle.productions[-1].schedule_granularity = "instance"
            bundle.productions[-1].raw_schedule_text = "Ticketmaster schedule"
        ticket_page.close()
        break

    page.close()
    return bundle
