from __future__ import annotations

"""Playwright scraper for Performance Space New York."""

import logging
import re
from datetime import date

from playwright.sync_api import BrowserContext

from ..models import ScrapeBundle
from ..schedule import collect_body_lines, infer_end_time, parse_performance_space_schedule_lines
from .common import body_lines, make_production, open_page, page_soup, series_from_production, ticket_link_from_page

THEATER_ID = "performance_space"
THEATER_NAME = "Performance Space New York"
SEED_URL = "https://performancespacenewyork.org/"
LOGGER = logging.getLogger("nyc_events_etl")


def scrape(context: BrowserContext) -> ScrapeBundle:
    listing_page = open_page(context, SEED_URL)
    cards = listing_page.eval_on_selector_all(
        'a[href*="/shows/"]',
        """els => els.map(a => ({href: a.href, text: (a.innerText || '').replace(/\\s+/g, ' ').trim()}))""",
    )
    detail_items = []
    seen = set()
    for item in cards:
        href = item["href"]
        text = item["text"]
        if href in seen:
            continue
        if not re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text):
            continue
        seen.add(href)
        detail_items.append(item)
    LOGGER.info("Performance Space detail URLs discovered: %d", len(detail_items))
    bundle = ScrapeBundle()
    for item in detail_items:
        url = item["href"]
        LOGGER.info("Performance Space scraping detail page: %s", url)
        page = open_page(context, url)
        lines = collect_body_lines(page_soup(page).get_text("\n"))
        title = page.title().split("| Performance Space New York")[0].strip()
        run_range_text = next((line for line in lines if re.search(r"\b[A-Z][a-z]+ \d{1,2}\s*-\s*[A-Z][a-z]+ \d{1,2}\b", line)), "")
        if not run_range_text:
            text = item["text"]
            m = re.search(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:\s*-\s*(?:[A-Z][a-z]+ )?\d{1,2})?)", text)
            if m:
                run_range_text = m.group(1)
        venue_name = next((line for line in lines if "Theatre" in line or "Theater" in line), THEATER_NAME)
        description = ""
        for idx, line in enumerate(lines):
            if line == title:
                for candidate in lines[idx + 1 : idx + 8]:
                    if candidate not in {run_range_text, venue_name, "Tickets!"} and len(candidate.split()) > 8:
                        description = candidate
                        break
                break
        bundle.productions.append(
            make_production(
                theater_id=THEATER_ID,
                theater_name=THEATER_NAME,
                title=title,
                description=description,
                source_url=url,
                venue_name=venue_name,
                ticket_url=ticket_link_from_page(page),
                schedule_source_url=url,
                run_range_text=run_range_text,
            )
        )
        pairs = parse_performance_space_schedule_lines(lines)
        LOGGER.info("Performance Space %s extracted %d explicit instances", title, len(pairs))
        if pairs:
            grouped = {}
            for perf_date, perf_time in pairs:
                grouped.setdefault(perf_date, []).append(perf_time)
            production = bundle.productions[-1]
            for perf_date, perf_times in sorted(grouped.items()):
                perf_times = sorted(set(perf_times))
                bundle.series.append(
                    series_from_production(
                        production,
                        dates=[perf_date],
                        start_times=perf_times,
                        end_time=infer_end_time(perf_times[0], duration_minutes=90),
                    )
                )
            production.schedule_granularity = "instance"
            production.raw_schedule_text = " | ".join(lines[:160])
        page.close()
    listing_page.close()
    return bundle
