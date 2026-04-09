from __future__ import annotations

"""Playwright scraper for the wild project."""

import logging
import re

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import collect_body_lines, infer_end_time, parse_clock_time, parse_month_day_range_year
from .common import body_lines, make_production, open_page, same_domain_links, series_from_production, ticket_link_from_page

THEATER_ID = "wild_project"
THEATER_NAME = "wild project"
SEED_URL = "https://thewildproject.org/performances/"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)
    detail_urls = [
        url for url in same_domain_links(listing_page, include="/performances/")
        if url.rstrip("/") != SEED_URL.rstrip("/")
        and "#" not in url
        and "/page/" not in url
        and not url.endswith("/current-performance/")
    ]
    LOGGER.info("wild project detail URLs discovered: %d", len(detail_urls))
    listing_page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("wild project scraping detail page: %s", url)
        page = open_page(context, url)
        lines = body_lines(page)
        if not lines:
            page.close()
            continue
        title = page.title().replace(" - wild project", "").strip()
        date_line = next((line for line in lines if re.search(rf"{re.escape('May')}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec", line, re.I) and re.search(r"\d{4}", line)), "")
        time_line = next((line for line in lines if re.fullmatch(r"\d{1,2}:\d{2}\s*(?:am|pm)", line, re.I)), "")
        price_line = next((line for line in lines if "Tickets" in line), "")
        description = ""
        if title in lines:
            idx = lines.index(title)
            for candidate in lines[idx + 1 : idx + 8]:
                if candidate not in {date_line, time_line, price_line} and len(candidate.split()) > 8:
                    description = candidate
                    break
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=THEATER_NAME,
            price=price_line,
            ticket_url=ticket_link_from_page(page),
            schedule_source_url=url,
            raw_schedule_text=" | ".join(line for line in (date_line, time_line, price_line) if line),
            run_range_text=date_line,
            schedule_granularity="instance" if date_line and time_line else "run_range",
        )
        bundle.productions.append(production)
        if date_line and time_line:
            try:
                perf_time = parse_clock_time(time_line)
                for perf_date in parse_month_day_range_year(date_line, default_year=None):
                    bundle.series.append(
                        series_from_production(
                            production,
                            dates=[perf_date],
                            start_times=[perf_time],
                            end_time=infer_end_time(perf_time, duration_minutes=90),
                        )
                    )
            except ValueError:
                bundle.warnings.append(f"{url}: unsupported schedule text {date_line!r} / {time_line!r}")
        page.close()
    return bundle
