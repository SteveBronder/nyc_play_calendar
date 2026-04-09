from __future__ import annotations

"""Playwright scraper for New York Theatre Workshop."""

from datetime import time
import logging
import re

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import collect_body_lines, infer_end_time, parse_nytw_ticket_calendar
from .common import body_lines, make_production, meta_content, open_page, page_soup, series_from_production, same_domain_links, ticket_link_from_page

THEATER_ID = "nytw"
THEATER_NAME = "New York Theatre Workshop"
SEED_URL = "https://www.nytw.org/2025-26-season/"
DEFAULT_VENUE = "New York Theatre Workshop"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)
    detail_urls = [
        url for url in same_domain_links(listing_page, include="/show/", exclude=("/tickets/",))
        if "/show/" in url
    ]
    LOGGER.info("NYTW detail URLs discovered: %d", len(detail_urls))
    listing_page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("NYTW scraping detail page: %s", url)
        page = open_page(context, url)
        title = page.locator("h1").first.inner_text() if page.locator("h1").count() else page.title()
        description = meta_content(page, 'meta[property="og:description"]')
        run_range_text = ""
        for line in body_lines(page):
            if re.search(r"\d{4}/\d{2} SEASON", line, re.I):
                continue
            if re.search(r"\w+ \d{1,2}, \d{4}.+\w+ \d{1,2}, \d{4}", line) or re.search(r"\w+ \d{1,2}, \d{4}[—-]\w+ \d{1,2}, \d{4}", line):
                run_range_text = line
                break
        ticket_url = ticket_link_from_page(page)
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=DEFAULT_VENUE,
            ticket_url=ticket_url,
            schedule_source_url=ticket_url or url,
            run_range_text=run_range_text,
        )
        bundle.productions.append(production)

        if ticket_url and "/tickets/" in ticket_url:
            LOGGER.info("NYTW opening ticket page: %s", ticket_url)
            ticket_page = open_page(context, ticket_url)
            ticket_lines = collect_body_lines(ticket_page.locator("body").inner_text())
            pairs = parse_nytw_ticket_calendar(ticket_lines)
            LOGGER.info("NYTW %s extracted %d ticket instances", title, len(pairs))
            if pairs:
                times = {}
                for perf_date, perf_time in pairs:
                    times.setdefault(perf_date, []).append(perf_time)
                for perf_date, perf_times in times.items():
                    perf_times = sorted(set(perf_times))
                    bundle.series.append(
                        series_from_production(
                            production,
                            dates=[perf_date],
                            start_times=perf_times,
                            end_time=infer_end_time(perf_times[0], duration_minutes=90),
                        )
                    )
                bundle.productions[-1].schedule_granularity = "instance"
                bundle.productions[-1].raw_schedule_text = " | ".join(ticket_lines[:80])
            ticket_page.close()
        page.close()
    return bundle
