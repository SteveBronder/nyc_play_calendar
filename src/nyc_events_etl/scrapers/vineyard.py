from __future__ import annotations

"""Playwright scraper for Vineyard Theatre."""

import logging
import re

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import collect_body_lines, infer_end_time, parse_vineyard_schedule_lines
from .common import body_lines, make_production, meta_content, open_page, series_from_production, same_domain_links, ticket_link_from_page

THEATER_ID = "vineyard"
THEATER_NAME = "Vineyard Theatre"
SEED_URL = "https://vineyardtheatre.org/showsevents/"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)
    detail_urls = same_domain_links(listing_page, include="/shows/", exclude=("/showsevents/",))
    LOGGER.info("Vineyard detail URLs discovered: %d", len(detail_urls))
    listing_page.close()

    bundle = ScrapeBundle()
    for url in detail_urls:
        LOGGER.info("Vineyard scraping detail page: %s", url)
        page = open_page(context, url)
        title = page.locator("h1").first.inner_text() if page.locator("h1").count() else page.title()
        description = meta_content(page, 'meta[property="og:description"]')
        run_range_text = next((line for line in body_lines(page) if re.search(r"\b[A-Z][a-z]+ \d{1,2}\s*-\s*[A-Z][a-z]+ \d{1,2}\b", line)), "")
        ticket_url = ticket_link_from_page(page)
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=title,
            description=description,
            source_url=url,
            venue_name=THEATER_NAME,
            ticket_url=ticket_url,
            schedule_source_url=ticket_url or url,
            run_range_text=run_range_text,
        )
        bundle.productions.append(production)
        if ticket_url and "boxoffice.vineyardtheatre.org" in ticket_url:
            LOGGER.info("Vineyard opening box office page: %s", ticket_url)
            ticket_page = open_page(context, ticket_url)
            pairs = parse_vineyard_schedule_lines(collect_body_lines(ticket_page.locator("body").inner_text()))
            LOGGER.info("Vineyard %s extracted %d ticket instances", title, len(pairs))
            if pairs:
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
                            end_time=infer_end_time(perf_times[0], duration_minutes=110),
                        )
                    )
                bundle.productions[-1].schedule_granularity = "instance"
                bundle.productions[-1].raw_schedule_text = " | ".join(collect_body_lines(ticket_page.locator("body").inner_text())[:120])
            ticket_page.close()
        else:
            LOGGER.info("Vineyard no box office link found for %s", title)
        page.close()
    return bundle
