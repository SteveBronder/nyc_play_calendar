from __future__ import annotations

"""Playwright scraper for Theater for the New City."""

import logging
import re

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import expand_weekly_schedule, extract_range_and_recurrence, infer_end_time
from .common import body_lines, make_production, open_page, same_domain_links, series_from_production, ticket_link_from_page

THEATER_ID = "tnc"
THEATER_NAME = "Theater for the New City"
SEED_URL = "https://theaterforthenewcity.net/whats-playing/"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)
    detail_urls = same_domain_links(listing_page, include="/shows/")
    LOGGER.info("TNC detail URLs discovered: %d", len(detail_urls))
    listing_page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("TNC scraping detail page: %s", url)
        page = open_page(context, url)
        lines = body_lines(page)
        title = page.locator("h1").first.inner_text() if page.locator("h1").count() else page.title()
        schedule_line = next(
            (
                line
                for line in lines
                if " at " in line.lower()
                and (
                    re.search(r"[A-Z]{3}\s+\d{1,2}\s*-\s*[A-Z]{3}\s+\d{1,2}", line)
                    or re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*-\s*", line, re.I)
                )
            ),
            "",
        )
        description = ""
        for idx, line in enumerate(lines):
            if line == title:
                for candidate in lines[idx + 1 : idx + 8]:
                    if candidate != schedule_line and len(candidate.split()) > 8:
                        description = candidate
                        break
                break
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=THEATER_NAME,
            ticket_url=ticket_link_from_page(page),
            schedule_source_url=url,
            raw_schedule_text=schedule_line,
            run_range_text=schedule_line.split(";")[0].strip() if ";" in schedule_line else schedule_line,
            schedule_granularity="instance" if schedule_line else "run_range",
        )
        bundle.productions.append(production)
        split = extract_range_and_recurrence(schedule_line) if schedule_line else None
        if split:
            range_text, recurrence = split
            pairs = expand_weekly_schedule(range_text, recurrence, default_year=2026)
            grouped = {}
            for perf_date, perf_time in pairs:
                grouped.setdefault(perf_date, []).append(perf_time)
            for perf_date, perf_times in grouped.items():
                perf_times = sorted(set(perf_times))
                bundle.series.append(
                    series_from_production(
                        production,
                        dates=[perf_date],
                        start_times=perf_times,
                        end_time=infer_end_time(perf_times[0], duration_minutes=120),
                    )
                )
        page.close()
    return bundle
