from __future__ import annotations

"""Artifact and static-site generation for scraped theater data."""

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .models import EventInstance, TheaterProduction

NY_TZ = ZoneInfo("America/New_York")

SITE_CSS = """
:root {
  --bg: #f4ecdf;
  --paper: rgba(255, 250, 243, 0.9);
  --card: #fffaf4;
  --ink: #231814;
  --muted: #705d55;
  --line: rgba(102, 69, 54, 0.14);
  --accent: #a33f2f;
  --accent-soft: rgba(163, 63, 47, 0.12);
  --olive: #59634d;
  --shadow: 0 22px 54px rgba(46, 27, 19, 0.09);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  color: var(--ink);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(163, 63, 47, 0.14), transparent 28%),
    radial-gradient(circle at bottom right, rgba(89, 99, 77, 0.12), transparent 26%),
    linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 52px;
}

.hero {
  padding: 34px 36px 26px;
  border: 1px solid var(--line);
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.78), rgba(255,246,236,0.92)),
    linear-gradient(90deg, rgba(163,63,47,0.08), rgba(89,99,77,0.06));
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
}

.eyebrow {
  margin: 0 0 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.72rem;
  color: var(--accent);
}

.hero h1 {
  margin: 0;
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
  font-size: clamp(2.4rem, 5vw, 4.8rem);
  line-height: 0.98;
  letter-spacing: -0.03em;
}

.subtitle {
  margin: 14px 0 0;
  max-width: 66ch;
  font-size: 1.02rem;
  line-height: 1.55;
  color: var(--muted);
}

.jump-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.jump-nav a {
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.62);
  color: var(--ink);
}

.layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 22px;
  margin-top: 26px;
}

.sidebar,
.content-panel {
  border: 1px solid var(--line);
  border-radius: 26px;
  background: var(--paper);
  box-shadow: var(--shadow);
}

.sidebar {
  padding: 22px 20px;
  align-self: start;
  position: sticky;
  top: 20px;
}

.sidebar h2,
.content-panel h2,
.production-card h2 {
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
}

.sidebar h2 {
  margin: 0 0 14px;
  font-size: 1.2rem;
}

.sidebar-list,
.production-list,
.schedule-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.sidebar-list li + li {
  margin-top: 10px;
}

.sidebar-list a {
  display: block;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,0.75);
  border: 1px solid transparent;
}

.sidebar-list a:hover {
  border-color: var(--line);
  text-decoration: none;
}

.sidebar-meta {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 0.92rem;
  color: var(--muted);
}

.content-panel {
  padding: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  margin-bottom: 18px;
}

.section-header h2 {
  margin: 0;
  font-size: 1.55rem;
}

.section-header p {
  margin: 0;
  color: var(--muted);
}

.filter-container {
  margin-bottom: 22px;
  padding: 20px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255,255,255,0.72), rgba(255,248,240,0.88));
  border: 1px solid var(--line);
  transition: all 0.3s ease;
}

.filter-container.active {
  background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,250,245,0.95));
  box-shadow: 0 4px 12px rgba(46, 27, 19, 0.08);
}

.filter-toggle-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: none;
  border-radius: 12px;
  background: rgba(163, 63, 47, 0.1);
  color: var(--accent);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  margin: 0;
}

.filter-toggle-btn:hover {
  background: rgba(163, 63, 47, 0.15);
  transform: translateX(2px);
}

.filter-toggle-btn .arrow {
  display: inline-block;
  width: 16px;
  height: 16px;
  transition: transform 0.3s ease;
}

.filter-toggle-btn.open .arrow {
  transform: rotate(180deg);
}

.filter-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: all 0.3s ease;
}

.filter-container.active .filter-controls {
  max-height: 300px;
  opacity: 1;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-group label {
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.filter-group input[type="date"] {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255,255,255,0.8);
  color: var(--ink);
  font-size: 0.95rem;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.filter-group input[type="date"]:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(163, 63, 47, 0.1);
}

.venue-select {
  position: relative;
  padding: 0;
}

.venue-select-trigger {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255,255,255,0.8);
  color: var(--ink);
  font-size: 0.95rem;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: border-color 0.2s ease;
}

.venue-select-trigger:hover {
  border-color: var(--muted);
}

.venue-select-trigger.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(163, 63, 47, 0.1);
}

.venue-select-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(46, 27, 19, 0.12);
  z-index: 10;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: all 0.3s ease;
}

.venue-select-dropdown.open {
  max-height: 200px;
  opacity: 1;
  overflow-y: auto;
}

.venue-option {
  padding: 10px 12px;
  border: none;
  background: none;
  color: var(--ink);
  font-size: 0.95rem;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  width: 100%;
  transition: background-color 0.2s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.venue-option:hover {
  background: rgba(163, 63, 47, 0.06);
}

.venue-option input[type="checkbox"] {
  cursor: pointer;
  accent-color: var(--accent);
}

.filter-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.filter-actions button {
  padding: 10px 16px;
  border: none;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.filter-apply {
  flex: 1;
  background: var(--accent);
  color: white;
}

.filter-apply:hover {
  background: #923226;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(163, 63, 47, 0.3);
}

.filter-reset {
  background: rgba(255,255,255,0.7);
  color: var(--muted);
  border: 1px solid var(--line);
}

.filter-reset:hover {
  background: rgba(255,255,255,0.9);
  color: var(--ink);
}

.production-list {
  display: grid;
  gap: 18px;
}

.production-card {
  padding: 22px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.86), rgba(255,250,245,0.94)),
    linear-gradient(135deg, rgba(163,63,47,0.04), rgba(89,99,77,0.04));
}

.production-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: start;
}

.production-head h2 {
  margin: 0;
  font-size: 1.6rem;
  line-height: 1.05;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.meta-row {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--muted);
  font-size: 0.93rem;
}

.run-range {
  display: inline-flex;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(89, 99, 77, 0.1);
  color: var(--olive);
}

.description {
  margin: 14px 0 0;
  color: var(--ink);
  line-height: 1.6;
}

.schedule-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.schedule-label {
  margin: 0 0 10px;
  font-size: 0.83rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
}

.schedule-list {
  display: grid;
  gap: 10px;
}

.schedule-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(102, 69, 54, 0.08);
}

.schedule-datetime {
  font-weight: 700;
}

.schedule-meta {
  margin-top: 3px;
  color: var(--muted);
  font-size: 0.9rem;
}

.schedule-links {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: end;
  font-size: 0.92rem;
}

.fallback-note {
  color: var(--muted);
  font-size: 0.94rem;
}

.venue-grid {
  display: grid;
  gap: 16px;
}

.venue-card {
  padding: 20px;
  border-radius: 22px;
  background:
    linear-gradient(145deg, rgba(255,255,255,0.86), rgba(255,248,239,0.95));
  border: 1px solid var(--line);
  transition: opacity 0.3s ease;
}

.venue-card.hidden {
  display: none;
}

.venue-card h3 {
  margin: 0;
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
  font-size: 1.55rem;
}

.venue-stats {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 0.93rem;
}

.show-preview {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.show-preview-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-top: 8px;
  border-top: 1px solid rgba(102, 69, 54, 0.08);
}

.show-preview-row:first-child {
  border-top: 0;
  padding-top: 0;
}

.show-preview-title {
  font-weight: 700;
}

.show-preview-meta {
  color: var(--muted);
  font-size: 0.9rem;
}

.empty-state {
  padding: 22px;
  border-radius: 18px;
  background: rgba(255,255,255,0.7);
  border: 1px dashed var(--line);
  color: var(--muted);
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }

  .filter-controls {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .shell {
    width: min(100vw - 20px, 1180px);
    padding-top: 18px;
  }

  .hero,
  .content-panel,
  .sidebar,
  .production-card,
  .venue-card,
  .filter-container {
    border-radius: 20px;
  }

  .hero {
    padding: 26px 22px;
  }

  .content-panel,
  .sidebar {
    padding: 18px;
  }

  .production-card {
    padding: 18px;
  }

  .filter-container {
    padding: 16px;
  }

  .filter-controls {
    grid-template-columns: 1fr;
  }

  .production-head,
  .section-header,
  .show-preview-row,
  .schedule-row {
    grid-template-columns: 1fr;
    display: grid;
  }

  .schedule-links {
    justify-content: start;
  }
}
"""


def _instance_payload(event: EventInstance) -> dict:
    payload = asdict(event)
    payload["start"] = event.start.isoformat()
    payload["end"] = event.end.isoformat()
    return payload


def _get_venue_date_range(productions: list[dict]) -> tuple[str | None, str | None]:
    """Extract earliest and latest dates from venue productions."""
    all_dates = []
    for production in productions:
        for instance in production.get("instances", []):
            if instance.get("start"):
                all_dates.append(instance["start"])

    if not all_dates:
        return None, None

    all_dates.sort()
    return all_dates[0][:10], all_dates[-1][:10]  # ISO date format


def write_artifact(
    productions: Iterable[TheaterProduction],
    instances: Iterable[EventInstance],
    destination: Path,
) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    prod_list = [asdict(prod) for prod in productions]
    instance_list = [_instance_payload(event) for event in instances]
    payload = {
        "scraped_at": datetime.now(NY_TZ).isoformat(),
        "production_count": len(prod_list),
        "instance_count": len(instance_list),
        "productions": prod_list,
        "instances": instance_list,
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_artifact(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render_site(payload: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    theater_map = {prod["theater_id"]: prod["theater_name"] for prod in payload["productions"]}
    grouped = _group_payload(payload)

    index_html = _render_index_page(payload, grouped, theater_map)
    (destination / "index.html").write_text(index_html, encoding="utf-8")

    theater_dir = destination / "theaters"
    theater_dir.mkdir(exist_ok=True)
    for theater_id, theater_name in sorted(theater_map.items(), key=lambda item: item[1]):
        theater_html = _render_theater_page(
            theater_id=theater_id,
            theater_name=theater_name,
            payload=payload,
            grouped=grouped.get(theater_id, []),
            theater_map=theater_map,
        )
        (theater_dir / f"{theater_id}.html").write_text(theater_html, encoding="utf-8")


def _group_payload(payload: dict) -> dict[str, list[dict]]:
    production_map = {}
    for production in payload["productions"]:
        copied = dict(production)
        copied["instances"] = []
        production_map[production["production_id"]] = copied

    for instance in sorted(payload["instances"], key=lambda item: item["start"]):
        production = production_map.get(instance["production_id"])
        if production:
            production["instances"].append(instance)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for production in production_map.values():
        grouped[production["theater_id"]].append(production)

    for theater_id, productions in grouped.items():
        productions.sort(
            key=lambda item: (
                item["instances"][0]["start"] if item["instances"] else "9999-12-31T23:59:59",
                item["title"],
            )
        )
    return grouped


def _render_index_page(payload: dict, grouped: dict[str, list[dict]], theater_map: dict[str, str]) -> str:
    venue_cards = []
    for theater_id, theater_name in sorted(theater_map.items(), key=lambda item: item[1]):
        productions = grouped.get(theater_id, [])
        preview = []
        for production in productions[:4]:
            next_show = production["instances"][0]["start"] if production["instances"] else production.get("run_range_text", "Schedule pending")
            # Extract date for filtering (ISO format)
            show_date = ""
            if production["instances"]:
                show_date = f' data-show-date="{next_show[:10]}"'
            preview.append(
                "\n".join(
                    [
                        f'<div class="show-preview-row"{show_date}>',
                        "<div>",
                        f'<div class="show-preview-title">{escape(production["title"])}</div>',
                        (
                            f'<div class="show-preview-meta">{escape(_format_start(next_show))}</div>'
                            if production["instances"]
                            else f'<div class="show-preview-meta">{escape(production.get("run_range_text") or "Schedule pending")}</div>'
                        ),
                        "</div>",
                        f'<a href="theaters/{escape(theater_id)}.html">View venue</a>',
                        "</div>",
                    ]
                )
            )
        preview_html = "".join(preview) if preview else '<div class="empty-state">No productions found.</div>'

        # Get date range for this venue
        earliest, latest = _get_venue_date_range(productions)
        data_attrs = ""
        if earliest and latest:
            data_attrs = f' data-earliest-date="{earliest}" data-latest-date="{latest}"'

        venue_cards.append(
            "\n".join(
                [
                    f'<article class="venue-card" data-venue="{escape(theater_id)}"{data_attrs}>',
                    f'<h3><a href="theaters/{escape(theater_id)}.html">{escape(theater_name)}</a></h3>',
                    '<div class="venue-stats">'
                    f'<span>{len(productions)} shows</span>'
                    f'<span>{sum(len(prod["instances"]) for prod in productions)} listed dates</span>'
                    "</div>",
                    f'<div class="show-preview">{preview_html}</div>',
                    "</article>",
                ]
            )
        )

    # Build filter HTML
    filter_html = _render_filter_panel(theater_map)

    body = "\n".join(
        [
            '<section class="content-panel">',
            '<div class="section-header">',
            "<div>",
            "<h2>Venue Guide</h2>",
            f"<p id=\"result-count\">{payload['production_count']} productions across {len(theater_map)} venues.</p>",
            "</div>",
            "</div>",
            filter_html,
            f'<div class="venue-grid" id="venueGrid">{"".join(venue_cards)}</div>',
            "</section>",
        ]
    )
    return _page_shell(
        title="NYC Small Theater Guide",
        eyebrow="Live Aggregation",
        subtitle=(
            f"{payload['instance_count']} scheduled performances collected from neighborhood venues. "
            "Browse by theater, then drill into each show to see upcoming dates and ticket links."
        ),
        theater_map=theater_map,
        main_content=body,
        include_filter_script=True,
    )


def _render_theater_page(
    *,
    theater_id: str,
    theater_name: str,
    payload: dict,
    grouped: list[dict],
    theater_map: dict[str, str],
) -> str:
    cards = [_render_production_card(production) for production in grouped]
    body = "\n".join(
        [
            '<section class="content-panel">',
            '<div class="section-header">',
            "<div>",
            f"<h2>{escape(theater_name)}</h2>",
            f"<p>{len(grouped)} productions and {sum(len(prod['instances']) for prod in grouped)} listed performance dates.</p>",
            "</div>",
            "</div>",
            (
                f'<ul class="production-list">{"".join(cards)}</ul>'
                if cards
                else '<div class="empty-state">No productions found for this theater.</div>'
            ),
            "</section>",
        ]
    )
    return _page_shell(
        title=theater_name,
        eyebrow="Venue Page",
        subtitle="Each show is grouped into a single card with its listed performance dates underneath.",
        theater_map=theater_map,
        main_content=body,
        active_theater_id=theater_id,
        back_link="../index.html",
        sidebar_note=f"Last scrape: {escape(_format_scraped_at(payload['scraped_at']))}",
    )


def _render_filter_panel(theater_map: dict[str, str]) -> str:
    """Generate the filter panel HTML."""
    venue_options = []
    for theater_id, theater_name in sorted(theater_map.items(), key=lambda item: item[1]):
        venue_options.append(
            f'<label class="venue-option"><input type="checkbox" class="venue-checkbox" value="{escape(theater_id)}" /> {escape(theater_name)}</label>'
        )

    return f"""<div class="filter-container" id="filterContainer">
  <button class="filter-toggle-btn" id="filterToggle">
    <span>✦ Filter by Date & Venue</span>
    <span class="arrow">▼</span>
  </button>

  <div class="filter-controls">
    <div class="filter-group">
      <label for="startDate">Start Date</label>
      <input type="date" id="startDate" />
    </div>

    <div class="filter-group">
      <label for="endDate">End Date</label>
      <input type="date" id="endDate" />
    </div>

    <div class="filter-group venue-select">
      <label for="venueSelect">Venues</label>
      <button class="venue-select-trigger" id="venueSelect">
        <span id="venueSelectText">All Venues</span>
        <span>▼</span>
      </button>
      <div class="venue-select-dropdown" id="venueSelectDropdown">
        <label class="venue-option">
          <input type="checkbox" class="venue-checkbox" value="all" /> Select All
        </label>
        {"".join(venue_options)}
      </div>
    </div>

    <div class="filter-actions">
      <button class="filter-apply" id="filterApply">Apply Filters</button>
      <button class="filter-reset" id="filterReset">Reset</button>
    </div>
  </div>
</div>"""


def _render_production_card(production: dict) -> str:
    instances = production["instances"]
    schedule_rows = []
    for instance in instances:
        schedule_rows.append(
            "\n".join(
                [
                    '<li class="schedule-row">',
                    "<div>",
                    f'<div class="schedule-datetime">{escape(_format_start(instance["start"]))}</div>',
                    f'<div class="schedule-meta">{escape(instance["venue_name"] or production["venue_name"] or production["theater_name"])}</div>',
                    "</div>",
                    '<div class="schedule-links">'
                    + (f'<a href="{escape(instance["source"])}">Source</a>' if instance["source"] else "")
                    + (" " if instance["source"] and instance["ticket_url"] else "")
                    + (f'<a href="{escape(instance["ticket_url"])}">Tickets</a>' if instance["ticket_url"] else "")
                    + "</div>",
                    "</li>",
                ]
            )
        )

    fallback = ""
    if not schedule_rows:
        links = []
        if production["source_url"]:
            links.append(f'<a href="{escape(production["source_url"])}">Source</a>')
        if production["ticket_url"]:
            links.append(f'<a href="{escape(production["ticket_url"])}">Tickets</a>')
        fallback = (
            '<div class="schedule-block">'
            '<p class="schedule-label">Schedule</p>'
            f'<p class="fallback-note">{escape(production.get("run_range_text") or "Specific dates are not exposed on the source site yet.")}</p>'
            f'<div class="schedule-links">{" ".join(links)}</div>'
            "</div>"
        )

    meta_parts = []
    if production["theater_name"]:
        meta_parts.append(escape(production["theater_name"]))
    if production["venue_name"] and production["venue_name"] != production["theater_name"]:
        meta_parts.append(escape(production["venue_name"]))
    if production.get("price"):
        meta_parts.append(escape(production["price"]))

    description = ""
    if production.get("description"):
        description = f'<p class="description">{escape(_truncate(production["description"], 320))}</p>'

    return "\n".join(
        [
            '<li class="production-card">',
            '<div class="production-head">',
            "<div>",
            f'<h2>{escape(production["title"])}</h2>',
            f'<div class="meta-row">{"".join(f"<span>{part}</span>" for part in meta_parts)}</div>',
            "</div>",
            (
                f'<div class="tag">{len(instances)} dates listed</div>'
                if instances
                else '<div class="tag">Run range only</div>'
            ),
            "</div>",
            (
                f'<div class="meta-row"><span class="run-range">{escape(production["run_range_text"])}</span></div>'
                if production.get("run_range_text")
                else ""
            ),
            description,
            (
                '<div class="schedule-block"><p class="schedule-label">Upcoming Dates</p>'
                f'<ul class="schedule-list">{"".join(schedule_rows)}</ul></div>'
                if schedule_rows
                else fallback
            ),
            "</li>",
        ]
    )


def _get_filter_script() -> str:
    """Generate the filter JavaScript."""
    return """<script>
    const filterState = {
      startDate: null,
      endDate: null,
      venues: new Set()
    };

    const filterContainer = document.getElementById('filterContainer');
    const filterToggle = document.getElementById('filterToggle');
    const filterApply = document.getElementById('filterApply');
    const filterReset = document.getElementById('filterReset');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const venueSelect = document.getElementById('venueSelect');
    const venueSelectDropdown = document.getElementById('venueSelectDropdown');
    const venueSelectText = document.getElementById('venueSelectText');
    const venueCheckboxes = document.querySelectorAll('.venue-checkbox');
    const venueGrid = document.getElementById('venueGrid');
    const resultCount = document.getElementById('result-count');

    // Store initial state
    const initialResultText = resultCount.textContent;
    const initialVenueCount = venueGrid.querySelectorAll('.venue-card').length;

    // Toggle Filter Panel
    filterToggle.addEventListener('click', () => {
      filterContainer.classList.toggle('active');
      filterToggle.classList.toggle('open');
    });

    // Venue Select Dropdown
    venueSelect.addEventListener('click', (e) => {
      e.stopPropagation();
      venueSelectDropdown.classList.toggle('open');
      venueSelect.classList.toggle('active');
    });

    document.addEventListener('click', (e) => {
      if (!venueSelect.contains(e.target) && !venueSelectDropdown.contains(e.target)) {
        venueSelectDropdown.classList.remove('open');
        venueSelect.classList.remove('active');
      }
    });

    // Venue Checkbox Logic
    venueCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        if (checkbox.value === 'all') {
          const isChecked = checkbox.checked;
          venueCheckboxes.forEach(cb => {
            if (cb.value !== 'all') {
              cb.checked = isChecked;
              if (isChecked) {
                filterState.venues.add(cb.value);
              } else {
                filterState.venues.delete(cb.value);
              }
            }
          });
        } else {
          if (checkbox.checked) {
            filterState.venues.add(checkbox.value);
          } else {
            filterState.venues.delete(checkbox.value);
          }
        }
        updateVenueSelectText();
      });
    });

    function updateVenueSelectText() {
      if (filterState.venues.size === 0) {
        venueSelectText.textContent = 'All Venues';
      } else if (filterState.venues.size === 7) {
        venueSelectText.textContent = 'All Venues';
      } else if (filterState.venues.size === 1) {
        const venueName = Array.from(filterState.venues)[0].replace(/_/g, ' ').toUpperCase();
        venueSelectText.textContent = venueName;
      } else {
        venueSelectText.textContent = filterState.venues.size + ' venues selected';
      }
    }

    // Apply Filters
    filterApply.addEventListener('click', applyFilters);

    function applyFilters() {
      filterState.startDate = startDateInput.value ? new Date(startDateInput.value) : null;
      filterState.endDate = endDateInput.value ? new Date(endDateInput.value) : null;

      const cards = document.querySelectorAll('.venue-card');
      let visibleCount = 0;

      cards.forEach(card => {
        const venue = card.getAttribute('data-venue');
        const earliestDate = card.getAttribute('data-earliest-date');
        const latestDate = card.getAttribute('data-latest-date');

        const isVenueMatch = filterState.venues.size === 0 || filterState.venues.has(venue);

        let isDateMatch = true;
        if (filterState.startDate || filterState.endDate) {
          if (earliestDate && latestDate) {
            const cardEarliestDate = new Date(earliestDate);
            const cardLatestDate = new Date(latestDate);

            if (filterState.startDate && cardLatestDate < filterState.startDate) {
              isDateMatch = false;
            }
            if (filterState.endDate && cardEarliestDate > filterState.endDate) {
              isDateMatch = false;
            }
          } else {
            isDateMatch = false;
          }
        }

        const shouldShow = isVenueMatch && isDateMatch;
        if (shouldShow) {
          card.classList.remove('hidden');

          // Hide individual show preview rows that fall outside date range
          const previewRows = card.querySelectorAll('.show-preview-row');
          let hasVisibleShow = false;
          previewRows.forEach(row => {
            const showDate = row.getAttribute('data-show-date');
            let showVisible = true;

            if (filterState.startDate || filterState.endDate) {
              if (showDate) {
                const rowDate = new Date(showDate);
                if (filterState.startDate && rowDate < filterState.startDate) {
                  showVisible = false;
                }
                if (filterState.endDate && rowDate > filterState.endDate) {
                  showVisible = false;
                }
              } else {
                // Hide undated rows when date filter is applied
                showVisible = false;
              }
            }

            row.style.display = showVisible ? 'flex' : 'none';
            if (showVisible) hasVisibleShow = true;
          });

          // Only count venue if it has at least one visible show
          if (hasVisibleShow || previewRows.length === 0) {
            visibleCount++;
          } else {
            card.classList.add('hidden');
          }
        } else {
          card.classList.add('hidden');
        }
      });

      updateResultCount(visibleCount);
    }

    // Reset Filters
    filterReset.addEventListener('click', () => {
      startDateInput.value = '';
      endDateInput.value = '';
      venueCheckboxes.forEach(cb => cb.checked = false);
      filterState.venues.clear();
      updateVenueSelectText();
      venueGrid.querySelectorAll('.venue-card').forEach(card => {
        card.classList.remove('hidden');
        // Show all show preview rows
        card.querySelectorAll('.show-preview-row').forEach(row => {
          row.style.display = 'flex';
        });
      });
      resultCount.textContent = initialResultText;
    });

    function updateResultCount(count) {
      const total = venueGrid.querySelectorAll('.venue-card').length;
      if (count === total) {
        resultCount.textContent = initialResultText;
      } else {
        resultCount.textContent = count + ' of ' + total + ' venues shown.';
      }
    }

    // Set min date to today
    const today = new Date().toISOString().split('T')[0];
    startDateInput.min = today;
    endDateInput.min = today;
  </script>"""


def _page_shell(
    *,
    title: str,
    eyebrow: str,
    subtitle: str,
    theater_map: dict[str, str],
    main_content: str,
    active_theater_id: str = "",
    back_link: str = "",
    sidebar_note: str = "",
    include_filter_script: bool = False,
) -> str:
    theater_links = []
    for theater_id, theater_name in sorted(theater_map.items(), key=lambda item: item[1]):
        label = theater_name
        if theater_id == active_theater_id:
            label = f"{theater_name} · current"
        href = f"theaters/{theater_id}.html" if not back_link else f"{theater_id}.html"
        theater_links.append(f'<li><a href="{escape(href)}">{escape(label)}</a></li>')

    back = f'<p><a href="{escape(back_link)}">Back to all theaters</a></p>' if back_link else ""
    sidebar = "\n".join(
        [
            '<aside class="sidebar">',
            "<h2>Browse Theaters</h2>",
            f'<ul class="sidebar-list">{"".join(theater_links)}</ul>',
            f'<div class="sidebar-meta">{sidebar_note or "Schedules link directly back to the venue source and ticket page when available."}</div>',
            "</aside>",
        ]
    )

    filter_script = ""
    if include_filter_script:
        filter_script = _get_filter_script()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{SITE_CSS}</style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      {back}
      <p class="eyebrow">{escape(eyebrow)}</p>
      <h1>{escape(title)}</h1>
      <p class="subtitle">{escape(subtitle)}</p>
      <nav class="jump-nav">
        <a href="{escape(back_link or 'index.html')}">Overview</a>
      </nav>
    </header>
    <div class="layout">
      {sidebar}
      {main_content}
    </div>
  </div>
  {filter_script}
</body>
</html>
"""


def _format_start(start_text: str) -> str:
    dt = datetime.fromisoformat(start_text)
    return dt.strftime("%a, %b %d at %I:%M %p")


def _format_scraped_at(scraped_at: str) -> str:
    dt = datetime.fromisoformat(scraped_at)
    return dt.strftime("%b %d, %Y at %I:%M %p")


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] + "…"
