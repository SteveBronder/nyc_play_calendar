from __future__ import annotations

"""Playwright scraper for The Slipper Room (Wix Events calendar)."""

import logging
import re
from datetime import date, time

from playwright.sync_api import BrowserContext, Page, TimeoutError as PwTimeout

from ..models import ScrapeBundle
from ..schedule import infer_end_time, parse_clock_time, parse_month_day_year
from .common import (
    clean_text,
    make_production,
    open_page,
    series_from_production,
)

THEATER_ID = "slipper_room"
THEATER_NAME = "The Slipper Room"
SEED_URL = "https://www.slipperroom.com/calendar"
DEFAULT_VENUE = "The Slipper Room"
DEFAULT_VENUE_ADDRESS = "167 Orchard Street, New York, NY 10002"
LOGGER = logging.getLogger("nyc_events_etl")

# Month names for regex
_MONTH_NAMES = (
    r"(?:January|February|March|April|May|June|July|August"
    r"|September|October|November|December)"
)

# Pattern for the Wix date string: "Apr 18, 2026, 8:00 PM"
_WIX_DATETIME_RE = re.compile(
    r"([A-Z][a-z]{2}\s+\d{1,2},\s*\d{4}),\s*(\d{1,2}:\d{2}\s*[AP]M)",
    re.I,
)

# Pattern to extract title from "Title. Month Day" or "Title Month Day"
_TITLE_DATE_RE = re.compile(
    rf"^(.+?)\.?\s+{_MONTH_NAMES}\s+\d{{1,2}}$",
    re.I,
)


def _parse_wix_datetime(text: str) -> tuple[date, time] | None:
    """Parse Wix-format datetime like ``Apr 18, 2026, 8:00 PM``."""
    m = _WIX_DATETIME_RE.search(text)
    if not m:
        return None
    try:
        d = parse_month_day_year(m.group(1))
        t = parse_clock_time(m.group(2))
        return d, t
    except (ValueError, KeyError):
        return None


def _strip_date_suffix(title_text: str) -> str:
    """Remove trailing '. Month Day' or ' Month Day' from an event title."""
    m = _TITLE_DATE_RE.match(title_text)
    return m.group(1).strip() if m else title_text.strip()


def _extract_events_from_grid(page: Page) -> list[dict]:
    """Extract event stubs (title, date, time) from all visible calendar cells.

    Uses JavaScript to efficiently read all cell data at once, avoiding
    repeated click/wait cycles.
    """
    raw_events = page.evaluate("""() => {
        const cells = document.querySelectorAll('[data-hook^="calendar-cell-"]');
        const results = [];
        for (const cell of cells) {
            const aria = cell.getAttribute('aria-label') || '';
            if (!/\\d+\\s+events?/.test(aria)) continue;

            // The data-hook contains the ISO date
            const hook = cell.getAttribute('data-hook') || '';
            const isoMatch = hook.match(/calendar-cell-(\\d{4}-\\d{2}-\\d{2})/);
            const cellDate = isoMatch ? isoMatch[1] : '';

            // Inner text contains event snippets: "18\\n8:00 PM\\nTitle. April 18\\n+1 more"
            const text = cell.innerText || '';
            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);

            // Parse event entries from the lines
            // Pattern: time line followed by title line
            const events = [];
            for (let i = 0; i < lines.length; i++) {
                const timePat = /^(\\d{1,2}:\\d{2}\\s*[AP]M)$/i;
                const timeMatch = lines[i].match(timePat);
                if (timeMatch && i + 1 < lines.length) {
                    const title = lines[i + 1];
                    if (title !== '+1 more' && title !== '+2 more' && title !== '+3 more') {
                        events.push({time: timeMatch[1], title: title, cellDate: cellDate});
                    }
                    i++; // skip the title line
                }
            }
            results.push(...events);
        }
        return results;
    }""")

    LOGGER.info("Slipper Room: extracted %d event stubs from grid", len(raw_events))
    return raw_events


def _click_and_extract_remaining(page: Page) -> list[dict]:
    """Click cells with '+N more' to discover events hidden behind the overlay.

    For cells that show "+1 more" (or +2 etc.), click the cell to open
    the popup list and extract the additional event titles/times.
    """
    additional: list[dict] = []
    cells = page.locator('[data-hook^="calendar-cell-"]')
    count = cells.count()

    for i in range(count):
        cell = cells.nth(i)
        aria = cell.get_attribute("aria-label") or ""
        text = cell.inner_text()

        # Only process cells with "+N more"
        if "+1 more" not in text and "+2 more" not in text and "+3 more" not in text:
            continue

        # Extract date from data-hook
        hook = cell.get_attribute("data-hook") or ""
        iso_m = re.search(r"calendar-cell-(\d{4}-\d{2}-\d{2})", hook)
        cell_date = iso_m.group(1) if iso_m else ""

        try:
            cell.click(timeout=5000)
            page.wait_for_timeout(1000)
        except PwTimeout:
            LOGGER.warning("Slipper Room: timeout clicking cell: %s", aria[:40])
            continue

        # The popup list appears inside the gridcell parent
        gridcell = cell.locator("..")
        popup_items = gridcell.locator("li")
        item_count = popup_items.count()

        # Extract all events from popup list
        for idx in range(item_count):
            item = popup_items.nth(idx)
            item_text = item.inner_text()
            lines = [l.strip() for l in item_text.split("\n") if l.strip()]
            # Lines: ["Title. Month Day", "8:00 PM"]
            title = ""
            ev_time = ""
            for line in lines:
                if re.fullmatch(r"\d{1,2}:\d{2}\s*[AP]M", line, re.I):
                    ev_time = line
                elif line and not re.fullmatch(r"\d{1,2}", line):
                    title = line
            if title:
                additional.append({"title": title, "time": ev_time, "cellDate": cell_date})

        # Close popup
        _close_popup(gridcell, page)

    return additional


def _close_popup(container, page: Page) -> None:
    """Close the event popup."""
    close_btn = container.locator("button").filter(has_text="Close")
    if close_btn.count() > 0:
        try:
            close_btn.first.click(timeout=3000)
            page.wait_for_timeout(400)
            return
        except PwTimeout:
            pass
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)


def _click_and_get_detail(page: Page, cell, event_title: str) -> dict | None:
    """Click a cell, then click a specific event to get its detail card data."""
    try:
        cell.click(timeout=5000)
        page.wait_for_timeout(1000)
    except PwTimeout:
        return None

    gridcell = cell.locator("..")

    # For single-event cells, the detail card shows directly
    # For multi-event cells, we need to click through the popup list
    popup_items = gridcell.locator("li")
    item_count = popup_items.count()

    if item_count > 0:
        # Find and click the matching event in the popup
        for idx in range(item_count):
            item = popup_items.nth(idx)
            item_text = item.inner_text()
            if event_title in item_text:
                try:
                    item.click(timeout=5000)
                    page.wait_for_timeout(1000)
                except PwTimeout:
                    _close_popup(gridcell, page)
                    return None
                break
        else:
            # Event not found in popup list
            _close_popup(gridcell, page)
            return None

    # Now extract detail card data
    detail = _extract_detail_card(gridcell, page)
    _close_popup(gridcell, page)
    return detail


def _extract_detail_card(container, page: Page) -> dict | None:
    """Extract event details from the visible detail card."""
    title_links = container.locator('a[href*="/event-details/"]')
    if title_links.count() == 0:
        return None

    title_link = title_links.first
    raw_title = title_link.inner_text()
    source_url = title_link.get_attribute("href") or ""
    if source_url and not source_url.startswith("http"):
        source_url = "https://www.slipperroom.com" + source_url

    card_text = container.inner_text()
    description = _extract_description(card_text, raw_title)

    ticket_url = source_url
    buy_links = container.locator("a").filter(has_text="Buy Tickets")
    if buy_links.count() > 0:
        href = buy_links.first.get_attribute("href") or ""
        if href:
            ticket_url = href if href.startswith("http") else "https://www.slipperroom.com" + href

    return {
        "description": clean_text(description),
        "ticket_url": ticket_url,
        "source_url": source_url,
    }


def _extract_description(card_text: str, raw_title: str) -> str:
    """Extract the description from the detail card text.

    The card text typically includes: day number, Back/Close, title,
    date/time, location, description, Buy Tickets.
    """
    lines = [line.strip() for line in card_text.split("\n") if line.strip()]
    description_lines: list[str] = []
    past_location = False
    for line in lines:
        if re.fullmatch(r"\d{1,2}", line):
            continue
        if line in ("Back", "Close", "Back Close"):
            continue
        if "Buy Tickets" in line:
            continue
        if raw_title and raw_title in line:
            continue
        if _WIX_DATETIME_RE.search(line):
            continue
        if "Orchard" in line or "10002" in line or line.startswith("New York,"):
            past_location = True
            continue
        if re.fullmatch(r"\+\d+ more", line):
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}\s*[AP]M", line, re.I):
            continue
        if past_location and len(line) > 10:
            description_lines.append(line)
    return " ".join(description_lines)


def _navigate_to_next_month(page: Page) -> str | None:
    """Navigate to the next month in the Wix Events calendar."""
    # Find the month label button
    month_label_btn = page.locator("button").filter(
        has_text=re.compile(
            r"^(?:January|February|March|April|May|June|July|August"
            r"|September|October|November|December)\s+\d{4}$"
        )
    )
    if month_label_btn.count() == 0:
        LOGGER.warning("Slipper Room: cannot find month selector")
        return None

    current_label = month_label_btn.first.inner_text().strip()
    m = re.match(r"(\w+)\s+(\d{4})", current_label)
    if not m:
        return None

    current_month_name = m.group(1)
    current_year = int(m.group(2))
    next_month_map = {
        "January": ("February", 0), "February": ("March", 0),
        "March": ("April", 0), "April": ("May", 0),
        "May": ("June", 0), "June": ("July", 0),
        "July": ("August", 0), "August": ("September", 0),
        "September": ("October", 0), "October": ("November", 0),
        "November": ("December", 0), "December": ("January", 1),
    }
    next_name, year_offset = next_month_map[current_month_name]
    next_year = current_year + year_offset
    target_label = f"{next_name} {next_year}"

    # Click the month button to open the picker
    try:
        month_label_btn.first.click(timeout=5000)
        page.wait_for_timeout(1000)
    except PwTimeout:
        LOGGER.warning("Slipper Room: timeout clicking month selector")
        return None

    # Try navigation arrows
    next_arrow = page.locator(
        '[data-hook="next-month-button"],'
        ' [aria-label*="next" i],'
        ' [aria-label*="Next"]'
    )
    if next_arrow.count() > 0:
        try:
            next_arrow.first.click(timeout=5000)
            page.wait_for_timeout(2000)
            return target_label
        except PwTimeout:
            pass

    # Try clicking month name
    next_month_option = page.locator(f'text="{next_name}"').first
    if next_month_option.count() > 0:
        try:
            next_month_option.click(timeout=5000)
            page.wait_for_timeout(2000)
            return target_label
        except PwTimeout:
            pass

    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    LOGGER.warning("Slipper Room: could not navigate to %s", target_label)
    return None


def scrape(context: BrowserContext) -> ScrapeBundle:
    """Scrape The Slipper Room calendar for current + next month."""
    page = open_page(context, SEED_URL)

    # Wait for calendar cells
    try:
        page.wait_for_selector('[data-hook^="calendar-cell-"]', timeout=15000)
        page.wait_for_timeout(2000)
    except PwTimeout:
        LOGGER.error("Slipper Room: calendar cells did not load")
        page.close()
        return ScrapeBundle(warnings=["Calendar cells did not load"])

    # Get current month label
    month_label_btn = page.locator("button").filter(
        has_text=re.compile(
            r"^(?:January|February|March|April|May|June|July|August"
            r"|September|October|November|December)\s+\d{4}$"
        )
    )
    current_month = "Current"
    if month_label_btn.count() > 0:
        current_month = month_label_btn.first.inner_text().strip()
    LOGGER.info("Slipper Room: starting with month: %s", current_month)

    # --- Phase 1: Extract event stubs from grid (fast, no clicking) ---
    all_stubs: list[dict] = []

    # Current month
    stubs = _extract_events_from_grid(page)
    all_stubs.extend(stubs)

    # Also get hidden events behind "+N more"
    more_stubs = _click_and_extract_remaining(page)
    all_stubs.extend(more_stubs)
    LOGGER.info("Slipper Room: %s total stubs (incl +more): %d", current_month, len(all_stubs))

    # Navigate to next month
    next_label = _navigate_to_next_month(page)
    if next_label:
        LOGGER.info("Slipper Room: navigated to %s", next_label)
        page.wait_for_timeout(2000)
        # Wait for new cells to appear
        try:
            page.wait_for_selector('[data-hook^="calendar-cell-"]', timeout=10000)
            page.wait_for_timeout(1000)
        except PwTimeout:
            LOGGER.warning("Slipper Room: calendar cells did not load for %s", next_label)

        stubs = _extract_events_from_grid(page)
        all_stubs.extend(stubs)
        more_stubs = _click_and_extract_remaining(page)
        all_stubs.extend(more_stubs)
        LOGGER.info("Slipper Room: %s total stubs (incl +more): %d", next_label, len(all_stubs))

    # --- Phase 2: Deduplicate stubs and parse date/time ---
    parsed_events: list[dict] = []
    seen: set[tuple] = set()
    for stub in all_stubs:
        raw_title = stub["title"]
        title = _strip_date_suffix(raw_title)
        cell_date_str = stub.get("cellDate", "")
        time_str = stub.get("time", "")

        event_date = None
        if cell_date_str:
            try:
                parts = cell_date_str.split("-")
                event_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                pass

        event_time = None
        if time_str:
            try:
                event_time = parse_clock_time(time_str)
            except ValueError:
                pass

        if not event_date:
            continue

        key = (title.lower(), str(event_date), str(event_time))
        if key in seen:
            continue
        seen.add(key)

        parsed_events.append({
            "title": title,
            "raw_title": raw_title,
            "date": event_date,
            "time": event_time,
            "description": "",
            "ticket_url": "",
            "source_url": "",
        })

    LOGGER.info("Slipper Room: %d unique parsed events", len(parsed_events))

    # --- Phase 3: Get descriptions by clicking into detail cards ---
    # Group events by cell date so we visit each cell at most once
    # For efficiency, only click into unique titles (recurring shows have same desc)
    title_details: dict[str, dict] = {}
    cells = page.locator('[data-hook^="calendar-cell-"]')
    cell_count = cells.count()

    # Navigate back to first month if we navigated away
    page.goto(SEED_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)

    # Build a set of unique titles that need details
    titles_needing_detail = set()
    for ev in parsed_events:
        if ev["title"].lower() not in title_details:
            titles_needing_detail.add(ev["title"].lower())

    # Visit each cell that has a title we need details for
    cells = page.locator('[data-hook^="calendar-cell-"]')
    cell_count = cells.count()

    for i in range(cell_count):
        if not titles_needing_detail:
            break

        cell = cells.nth(i)
        aria = cell.get_attribute("aria-label") or ""
        if not re.search(r"\d+\s+events?", aria):
            continue

        cell_text = cell.inner_text()
        # Check if any needed title appears in this cell
        found_title = None
        for needed in list(titles_needing_detail):
            if needed in cell_text.lower():
                found_title = needed
                break
        if not found_title:
            continue

        detail = _click_and_get_detail(page, cell, "")
        if detail:
            title_details[found_title] = detail
            titles_needing_detail.discard(found_title)
            LOGGER.info("Slipper Room: got detail for '%s'", found_title[:40])

    # If we still need details, try the next month too
    if titles_needing_detail:
        nav_result = _navigate_to_next_month(page)
        if nav_result:
            page.wait_for_timeout(2000)
            cells = page.locator('[data-hook^="calendar-cell-"]')
            cell_count = cells.count()
            for i in range(cell_count):
                if not titles_needing_detail:
                    break
                cell = cells.nth(i)
                aria = cell.get_attribute("aria-label") or ""
                if not re.search(r"\d+\s+events?", aria):
                    continue
                cell_text = cell.inner_text()
                found_title = None
                for needed in list(titles_needing_detail):
                    if needed in cell_text.lower():
                        found_title = needed
                        break
                if not found_title:
                    continue
                detail = _click_and_get_detail(page, cell, "")
                if detail:
                    title_details[found_title] = detail
                    titles_needing_detail.discard(found_title)

    page.close()

    # --- Phase 4: Merge details into events and build productions ---
    for ev in parsed_events:
        key = ev["title"].lower()
        if key in title_details:
            d = title_details[key]
            ev["description"] = d.get("description", "")
            ev["ticket_url"] = d.get("ticket_url", "")
            ev["source_url"] = d.get("source_url", "")

    # Group by title
    productions_map: dict[str, dict] = {}
    for ev in parsed_events:
        key = ev["title"].lower()
        if key not in productions_map:
            productions_map[key] = {
                "title": ev["title"],
                "description": ev["description"],
                "source_url": ev["source_url"],
                "ticket_url": ev["ticket_url"],
                "instances": [],
            }
        productions_map[key]["instances"].append((ev["date"], ev["time"]))
        if len(ev["description"]) > len(productions_map[key]["description"]):
            productions_map[key]["description"] = ev["description"]
        if ev["source_url"] and not productions_map[key]["source_url"]:
            productions_map[key]["source_url"] = ev["source_url"]
        if ev["ticket_url"] and not productions_map[key]["ticket_url"]:
            productions_map[key]["ticket_url"] = ev["ticket_url"]

    bundle = ScrapeBundle()
    for prod_data in productions_map.values():
        production = make_production(
            theater_id=THEATER_ID,
            theater_name=THEATER_NAME,
            title=prod_data["title"],
            description=prod_data["description"],
            source_url=prod_data["source_url"] or SEED_URL,
            venue_name=DEFAULT_VENUE,
            venue_address=DEFAULT_VENUE_ADDRESS,
            ticket_url=prod_data["ticket_url"],
            schedule_source_url=SEED_URL,
            schedule_granularity="instance",
        )
        bundle.productions.append(production)

        for perf_date, perf_time in prod_data["instances"]:
            start_times = [perf_time] if perf_time else []
            end_time = infer_end_time(perf_time, duration_minutes=120) if perf_time else None
            bundle.series.append(
                series_from_production(
                    production,
                    dates=[perf_date],
                    start_times=start_times,
                    end_time=end_time,
                )
            )

    LOGGER.info(
        "Slipper Room: scraped %d productions, %d event instances",
        len(bundle.productions),
        len(bundle.series),
    )
    return bundle
