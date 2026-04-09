from __future__ import annotations

"""Playwright scraper for Liberty Theatres."""

import logging

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import infer_end_time
from .common import body_lines, make_production, open_page, parse_ticketmaster_events, same_domain_links, series_from_production, ticket_link_from_page

THEATER_ID = "liberty"
THEATER_NAME = "Liberty Theatres"
SEED_URL = "https://www.libertytheatresusa.com/nowplaying/"
EXCLUDE = (
    "/about",
    "/contact",
    "/location",
    "/privacy",
    "/terms",
    "/theatrerental",
    "/accessibility",
    "/nowplaying/",
)
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    page = open_page(context, SEED_URL)
    detail_urls = [
        url for url in same_domain_links(page)
        if url.rstrip("/") != "https://www.libertytheatresusa.com" and all(fragment not in url for fragment in EXCLUDE)
    ]
    LOGGER.info("Liberty detail URLs discovered: %d", len(detail_urls))
    page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("Liberty scraping detail page: %s", url)
        page = open_page(context, url)
        if "Page not found" in page.title():
            page.close()
            continue
        lines = body_lines(page)
        title = next((line for line in lines if line and line.upper() not in {"ABOUT", "SHOWS & TICKETS", "RENTAL", "LOCATION", "CONTACT US"}), page.title())
        date_line = next((line for line in lines if line.startswith("DATE:")), "")
        location_line = next((line for line in lines if line.startswith("LOCATION:")), "")
        price_line = next((line for line in lines if "Ticket prices" in line or "TICKETS PRICING" in line), "")
        description = ""
        if title in lines:
            idx = lines.index(title)
            for candidate in lines[idx + 1 : idx + 6]:
                if not any(token in candidate for token in ("DATE:", "LOCATION:", "GET TICKETS", "Accessibility")):
                    description = candidate
                    break
        run_range_text = ""
        if date_line:
            idx = lines.index(date_line)
            if idx + 1 < len(lines):
                run_range_text = lines[idx + 1]
        venue_name = ""
        if location_line:
            idx = lines.index(location_line)
            if idx + 1 < len(lines):
                venue_name = lines[idx + 1]
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=venue_name or THEATER_NAME,
            price=price_line.replace("TICKETS PRICING:", "").replace("Ticket prices range from", "").strip(),
            ticket_url=ticket_link_from_page(page),
            schedule_source_url=url,
            run_range_text=run_range_text,
            raw_schedule_text=" | ".join(line for line in (run_range_text, price_line) if line),
        )
        bundle.productions.append(production)
        if production.ticket_url and "ticketmaster.com" in production.ticket_url:
            ticket_page = open_page(context, production.ticket_url)
            ticket_events = parse_ticketmaster_events(ticket_page)
            LOGGER.info("Liberty %s extracted %d Ticketmaster instances", title, len(ticket_events))
            grouped = {}
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
        page.close()
    return bundle
