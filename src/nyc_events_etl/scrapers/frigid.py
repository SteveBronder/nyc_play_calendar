from __future__ import annotations

"""Playwright scraper for Frigid NYC ticketed shows across multiple venues."""

import json
import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import infer_end_time
from .common import make_production, open_page, page_soup, series_from_production

THEATER_ID = "frigid"
SEED_URL = "https://tickets.frigid.nyc/"

# Maps venue name from site → theater_id for the guide
VENUE_ID_MAP = {
    "Under St. Marks": "under_st_marks",
    "Under St Marks": "under_st_marks",
    "Chain Theatre": "chain_theatre",
    "The Rat NYC": "rat_nyc",
    "Wild Project": "wild_project",
    "Parkside Lounge": "parkside_lounge",
}

NY_TZ = ZoneInfo("America/New_York")
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    """Scrape all Frigid NYC shows from tickets.frigid.nyc and categorize by venue."""

    page = open_page(context, SEED_URL)
    soup = page_soup(page)

    # Extract all show cards from the first col-lg-9 (avoid duplicate mobile layout)
    col = soup.find("div", class_="col-lg-9")
    if not col:
        LOGGER.warning("Frigid: could not find col-lg-9 container")
        page.close()
        return ScrapeBundle(warnings=["Could not find show container"])

    shows = []
    for card in col.find_all("div", class_="card"):
        title_elem = card.find("h4", class_="primary-color")
        venue_elem = card.find("p", class_="event-location")
        link_elem = card.find("a", href=lambda x: x and "/event/" in x)

        if not (title_elem and venue_elem and link_elem):
            continue

        title = title_elem.get_text(strip=True)
        venue = venue_elem.find("span", class_="one-line-clamp")
        venue_name = venue.get_text(strip=True) if venue else ""
        event_url = link_elem.get("href", "")

        if not event_url.startswith("http"):
            event_url = SEED_URL.rstrip("/") + event_url

        shows.append({
            "title": title,
            "venue": venue_name,
            "url": event_url,
        })

    LOGGER.info("Frigid: discovered %d shows", len(shows))
    page.close()

    # Group by venue
    by_venue = {}
    for show in shows:
        venue = show["venue"]
        if venue not in by_venue:
            by_venue[venue] = []
        by_venue[venue].append(show)

    LOGGER.info("Frigid: %d unique venues", len(by_venue))

    bundle = ScrapeBundle()

    # Process each venue
    for venue_name, shows_at_venue in sorted(by_venue.items()):
        theater_id = VENUE_ID_MAP.get(venue_name)
        if not theater_id:
            LOGGER.warning("Frigid: unknown venue '%s', skipping", venue_name)
            continue

        LOGGER.info("Frigid: processing %d shows at %s", len(shows_at_venue), venue_name)

        # Scrape each show at this venue
        for show_info in shows_at_venue:
            scrape_show(context, bundle, theater_id, venue_name, show_info)

    return bundle


def scrape_show(context: BrowserContext, bundle: ScrapeBundle, theater_id: str, venue_name: str, show_info: dict) -> None:
    """Scrape a single show page and add production + series to bundle."""

    title = show_info["title"]
    url = show_info["url"]

    try:
        page = open_page(context, url)
        soup = page_soup(page)

        # Extract data-performances JSON from div#event-data
        event_data_elem = soup.find("div", id="event-data")
        if not event_data_elem:
            LOGGER.warning("Frigid: no event-data found for %s at %s", title, url)
            page.close()
            return

        data_performances_json = event_data_elem.get("data-performances", "{}")
        try:
            data = json.loads(data_performances_json)
        except json.JSONDecodeError as e:
            LOGGER.warning("Frigid: failed to parse event data for %s: %s", title, e)
            page.close()
            return

        times_data = data.get("times", {})

        # Extract description from the page
        description = ""
        desc_elem = soup.find("p", class_="three-line-clamp")
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Get ticket URL - look for the event page itself as fallback
        ticket_url = url
        ticket_btn = soup.find("a", class_="btn", href=lambda x: x and "frigid" in x)
        if ticket_btn:
            ticket_url = ticket_btn.get("href", url)

        # Build production record
        production = make_production(
            theater_id=theater_id,
            theater_name=venue_name,
            title=title,
            description=description,
            source_url=url,
            venue_name=venue_name,
            ticket_url=ticket_url,
            schedule_source_url=url,
        )
        bundle.productions.append(production)

        # Extract performance dates and times
        # dates is list of "DD/MM/YYYY" strings
        dates_list = data.get("dates", [])

        for date_str in dates_list:
            # Parse "DD/MM/YYYY"
            try:
                dt = datetime.strptime(date_str, "%d/%m/%Y")
                perf_date = dt.date()
            except ValueError:
                LOGGER.warning("Frigid: invalid date format '%s' for %s", date_str, title)
                continue

            # Get all performances for this date
            perf_times = times_data.get(date_str, [])
            start_times = []

            for perf in perf_times:
                # Only include physical performances
                if perf.get("presentationFormat") != "PHYSICAL":
                    continue

                # Parse performanceRealTime like "2026-04-12 15:55:00"
                perf_real_time = perf.get("performanceRealTime", "")
                if not perf_real_time:
                    continue

                try:
                    dt = datetime.strptime(perf_real_time, "%Y-%m-%d %H:%M:%S")
                    start_times.append(dt.time())
                except ValueError:
                    LOGGER.warning("Frigid: invalid time format '%s' for %s", perf_real_time, title)

            # Create EventSeries for each (date, times) combo
            if start_times:
                start_times = sorted(set(start_times))  # Deduplicate and sort
                end_time = infer_end_time(start_times[0], duration_minutes=120)

                bundle.series.append(
                    series_from_production(
                        production,
                        dates=[perf_date],
                        start_times=start_times,
                        end_time=end_time,
                    )
                )

        if bundle.series and bundle.series[-1] and bundle.series[-1].production_id == production.production_id:
            production.schedule_granularity = "instance"

        LOGGER.info("Frigid: %s at %s extracted %d dates", title, venue_name, len(bundle.series))

        page.close()
    except Exception as e:
        LOGGER.exception("Frigid: failed to scrape %s: %s", title, e)
