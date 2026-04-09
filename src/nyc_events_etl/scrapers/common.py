from __future__ import annotations

"""Shared Playwright scraping helpers."""

from dataclasses import asdict
from datetime import datetime
from hashlib import md5
import json
import logging
from typing import Iterable, Sequence
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext, Page

from ..models import EventSeries, ScrapeBundle, TheaterProduction

LOGGER = logging.getLogger("nyc_events_etl")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def body_lines(page: Page) -> list[str]:
    return [clean_text(line) for line in page.locator("body").inner_text().splitlines() if clean_text(line)]


def page_soup(page: Page) -> BeautifulSoup:
    return BeautifulSoup(page.content(), "html.parser")


def json_ld_objects(page: Page) -> list[dict]:
    objects: list[dict] = []
    soup = page_soup(page)
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            if isinstance(payload.get("@graph"), list):
                objects.extend(item for item in payload["@graph"] if isinstance(item, dict))
            else:
                objects.append(payload)
        elif isinstance(payload, list):
            objects.extend(item for item in payload if isinstance(item, dict))
    return objects


def parse_ticketmaster_events_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    data_script = soup.find("script", id="__NEXT_DATA__")
    if not data_script:
        return []
    raw = data_script.string or data_script.get_text()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    page_props = payload.get("props", {}).get("pageProps", {})
    results: list[dict] = []
    seen: set[tuple] = set()

    def add_event(*, title: str, start_text: str, event_url: str, venue_name: str = "", venue_address: str = "", status: str = "") -> None:
        if "cancel" in status.lower():
            return
        if not start_text:
            return
        try:
            start_dt = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        except ValueError:
            return
        key = (clean_text(title), start_dt.isoformat(), event_url)
        if key in seen:
            return
        seen.add(key)
        results.append(
            {
                "title": clean_text(title),
                "date": start_dt.date(),
                "time": start_dt.time().replace(tzinfo=None),
                "event_url": event_url,
                "venue_name": clean_text(venue_name),
                "venue_address": clean_text(venue_address),
            }
        )

    state = page_props.get("initialReduxState") or {}
    api_queries = (state.get("api") or {}).get("queries") or {}
    for query in api_queries.values():
        if not isinstance(query, dict):
            continue
        data = query.get("data")
        if isinstance(data, list):
            event_groups = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            event_groups = [data]
        else:
            event_groups = []
        for group in event_groups:
            events = group.get("events") or []
            for event in events:
                venue = event.get("venue") or {}
                venue_address = ", ".join(
                    part
                    for part in (
                        venue.get("addressLineOne", ""),
                        venue.get("city", ""),
                        venue.get("state", ""),
                        venue.get("code", ""),
                    )
                    if part
                )
                add_event(
                    title=event.get("title", ""),
                    start_text=((event.get("dates") or {}).get("startDate", "")),
                    event_url=event.get("url", ""),
                    venue_name=venue.get("name", ""),
                    venue_address=venue_address,
                    status="cancelled" if event.get("cancelled") else "",
                )

    events_jsonld = page_props.get("eventsJsonLD") or []
    if len(events_jsonld) == 1 and isinstance(events_jsonld[0], list):
        events_jsonld = events_jsonld[0]
    for event in events_jsonld:
        if not isinstance(event, dict):
            continue
        offers = event.get("offers") or {}
        location = event.get("location") or {}
        address = location.get("address") or {}
        add_event(
            title=event.get("name", ""),
            start_text=event.get("startDate", ""),
            event_url=offers.get("url") or event.get("url", ""),
            venue_name=location.get("name", ""),
            venue_address=", ".join(
                part
                for part in (
                    address.get("streetAddress", ""),
                    address.get("addressLocality", ""),
                    address.get("addressRegion", ""),
                    address.get("postalCode", ""),
                )
                if part
            ),
            status=event.get("eventStatus", ""),
        )
    return results


def parse_ticketmaster_events(page: Page) -> list[dict]:
    return parse_ticketmaster_events_from_html(page.content())


def meta_content(page: Page, selector: str) -> str:
    locator = page.locator(selector).first
    if locator.count() == 0:
        return ""
    return clean_text(locator.get_attribute("content") or "")


def stable_id(*parts: str) -> str:
    key = "||".join(clean_text(part) for part in parts if part)
    return md5(key.encode("utf-8")).hexdigest()[:16]


def default_production_id(theater_id: str, title: str, source_url: str) -> str:
    return stable_id(theater_id, title, source_url)


def make_production(
    *,
    theater_id: str,
    theater_name: str,
    title: str,
    source_url: str,
    description: str = "",
    price: str = "",
    venue_name: str = "",
    venue_address: str = "",
    ticket_url: str = "",
    schedule_source_url: str = "",
    raw_schedule_text: str = "",
    run_range_text: str = "",
    schedule_granularity: str = "run_range",
    production_id: str = "",
) -> TheaterProduction:
    return TheaterProduction(
        production_id=production_id or default_production_id(theater_id, title, source_url),
        theater_id=theater_id,
        theater_name=theater_name,
        title=clean_text(title),
        description=clean_text(description),
        price=clean_text(price),
        venue_name=clean_text(venue_name),
        venue_address=clean_text(venue_address),
        source_url=source_url,
        ticket_url=ticket_url,
        schedule_source_url=schedule_source_url,
        raw_schedule_text=clean_text(raw_schedule_text),
        run_range_text=clean_text(run_range_text),
        schedule_granularity=schedule_granularity,
    )


def series_from_production(
    production: TheaterProduction,
    dates: Sequence,
    start_times: Sequence,
    end_time=None,
) -> EventSeries:
    return EventSeries(
        title=production.title,
        description=production.description,
        price=production.price,
        venue_name=production.venue_name,
        venue_address=production.venue_address,
        dates=list(dates),
        start_times=list(start_times),
        end_time=end_time,
        source=production.source_url,
        theater_id=production.theater_id,
        theater_name=production.theater_name,
        production_id=production.production_id,
        ticket_url=production.ticket_url,
        schedule_source_url=production.schedule_source_url or production.source_url,
        raw_schedule_text=production.raw_schedule_text,
        schedule_granularity="instance",
    )


def same_domain_links(page: Page, *, include: str = "", exclude: Iterable[str] = ()) -> list[str]:
    links = page.eval_on_selector_all(
        "a[href]",
        """els => els.map(a => a.href).filter(Boolean)""",
    )
    domain = urlparse(page.url).netloc
    deduped: list[str] = []
    seen: set[str] = set()
    for href in links:
        if urlparse(href).netloc != domain:
            continue
        if include and include not in href:
            continue
        if any(fragment in href for fragment in exclude):
            continue
        if href not in seen:
            deduped.append(href)
            seen.add(href)
    return deduped


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def ticket_link_from_page(page: Page) -> str:
    links = page.eval_on_selector_all(
        "a[href]",
        """els => els.map(a => ({href: a.href, text: (a.innerText || '').replace(/\\s+/g, ' ').trim()}))""",
    )
    preferred_hrefs = []
    for item in links:
        text = item["text"]
        href = item["href"]
        if any(
            needle in href
            for needle in (
                "/show/",
                "boxoffice.",
                "ovationtix.com",
                "ticketmaster.com",
                "EventAvailability",
            )
        ) and re.search(r"ticket|book now|buy", text, re.I):
            preferred_hrefs.append(href)
    if preferred_hrefs:
        return preferred_hrefs[0]
    for item in links:
        text = item["text"]
        href = item["href"]
        if re.search(r"ticket|book now|buy", text, re.I) and not re.search(r"policy", text, re.I):
            return href
    return ""


def open_page(context: BrowserContext, url: str) -> Page:
    LOGGER.info("Opening page: %s", url)
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2_000)
    LOGGER.info("Opened page: %s -> %s", url, page.title())
    return page


def merge_bundles(bundles: Iterable[ScrapeBundle]) -> ScrapeBundle:
    merged = ScrapeBundle()
    for bundle in bundles:
        merged.productions.extend(bundle.productions)
        merged.series.extend(bundle.series)
        merged.warnings.extend(bundle.warnings)
    return merged
