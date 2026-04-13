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

.layout > * { min-width: 0; }

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
  grid-template-columns: 1fr;
  gap: 16px;
  margin-top: 16px;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-height 0.35s ease, opacity 0.25s ease;
}

.filter-container.active .filter-controls {
  max-height: 700px;
  opacity: 1;
  overflow: visible;
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


.filter-reset {
  background: rgba(255,255,255,0.7);
  color: var(--muted);
  border: 1px solid var(--line);
}

.filter-reset:hover {
  background: rgba(255,255,255,0.9);
  color: var(--ink);
}

/* Calendar date picker */
.cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: .4rem;
  font-weight: 600;
  font-size: .95rem;
}
.cal-nav {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.5rem;
  color: var(--accent);
  padding: .1rem .35rem;
  border-radius: 6px;
  line-height: 1;
}
.cal-nav:hover { background: var(--accent-soft); }
.cal-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: .85rem;
}
.cal-table th {
  text-align: center;
  padding: .25rem 0;
  color: var(--muted);
  font-weight: 500;
  font-size: .77rem;
}
.cal-day {
  text-align: center;
  padding: .35rem .1rem;
  cursor: pointer;
  border-radius: 6px;
  user-select: none;
}
.cal-day:not(.other-month):hover { background: rgba(102, 69, 54, 0.07); }
.cal-day.has-show {
  font-weight: 700;
  color: var(--accent);
}
.cal-day.has-show:hover { background: var(--accent-soft); }
.cal-day.selected {
  background: var(--accent);
  color: #fff !important;
}
.cal-day.selected:hover { opacity: .85; }
.cal-day.other-month {
  opacity: .3;
  pointer-events: none;
  cursor: default;
}
.cal-day.today {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.cal-legend {
  display: flex;
  gap: 1rem;
  font-size: .75rem;
  color: var(--muted);
  margin-top: .4rem;
}
.cal-legend-item {
  display: flex;
  align-items: center;
  gap: .3rem;
}
.cal-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--accent);
}
.cal-dot-show { opacity: .45; }
.cal-presets {
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
  margin-bottom: .6rem;
}
.cal-preset {
  font: inherit;
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .02em;
  padding: .32rem .7rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel-soft, rgba(102, 69, 54, 0.04));
  color: var(--accent);
  cursor: pointer;
  transition: background .15s ease, color .15s ease, border-color .15s ease;
}
.cal-preset:hover {
  background: var(--accent-soft, rgba(102, 69, 54, 0.09));
  border-color: var(--accent);
}
.cal-preset:active { transform: translateY(1px); }

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

/* When a date filter is active, swap the single next-show line for the
   full list of matching performance dates. Populated client-side. */
.show-preview-dates {
  display: none;
  list-style: none;
  padding: 0;
  margin: .15rem 0 0 0;
  color: var(--muted);
  font-size: 0.85rem;
}
.show-preview-date {
  padding: 1px 0;
}
.show-preview-date.hidden { display: none; }
.show-preview-row.date-filtered .show-preview-meta { display: none; }
.show-preview-row.date-filtered .show-preview-dates { display: block; }

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
    # Drop any performance that already happened. The site is forward-looking;
    # past-dated shows should never appear in listings or in the date filter.
    today_str = datetime.now(NY_TZ).date().isoformat()

    production_map = {}
    for production in payload["productions"]:
        copied = dict(production)
        copied["instances"] = []
        production_map[production["production_id"]] = copied

    for instance in sorted(payload["instances"], key=lambda item: item["start"]):
        if instance.get("start", "")[:10] < today_str:
            continue
        production = production_map.get(instance["production_id"])
        if production:
            production["instances"].append(instance)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for production in production_map.values():
        # Hide productions whose entire run is in the past.
        if not production["instances"]:
            continue
        grouped[production["theater_id"]].append(production)

    for theater_id, productions in grouped.items():
        productions.sort(
            key=lambda item: (
                item["instances"][0]["start"],
                item["title"],
            )
        )
    return grouped


def _render_index_page(payload: dict, grouped: dict[str, list[dict]], theater_map: dict[str, str]) -> str:
    # grouped has already been filtered to upcoming-only in _group_payload.
    upcoming_production_count = sum(len(prods) for prods in grouped.values())
    upcoming_instance_count = sum(
        len(prod["instances"]) for prods in grouped.values() for prod in prods
    )

    venue_cards = []
    for theater_id, theater_name in sorted(theater_map.items(), key=lambda item: item[1]):
        productions = grouped.get(theater_id, [])
        if not productions:
            continue
        preview = []
        for production in productions[:4]:
            # _group_payload guarantees every production here has at least
            # one upcoming instance; past instances have already been filtered.
            instances = production["instances"]
            next_show = instances[0]["start"]
            all_inst_dates = sorted({inst["start"][:10] for inst in instances})
            show_date_attrs = (
                f' data-show-date="{next_show[:10]}"'
                f' data-all-dates="{",".join(all_inst_dates)}"'
            )
            # Every upcoming performance — shown in place of the single
            # next-show meta line when a date filter is active so users
            # can see every matching date for each show.
            dates_list = "".join(
                f'<li class="show-preview-date" data-date="{inst["start"][:10]}">{escape(_format_start(inst["start"]))}</li>'
                for inst in instances
            )
            preview.append(
                "\n".join(
                    [
                        f'<div class="show-preview-row"{show_date_attrs}>',
                        "<div>",
                        f'<div class="show-preview-title">{escape(production["title"])}</div>',
                        f'<div class="show-preview-meta">{escape(_format_start(next_show))}</div>',
                        f'<ul class="show-preview-dates">{dates_list}</ul>',
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

    # All unique show dates across every production — used to highlight calendar cells
    all_show_dates_json = json.dumps(sorted({
        inst["start"][:10]
        for prods in grouped.values()
        for prod in prods
        for inst in prod["instances"]
    }))

    body = "\n".join(
        [
            '<section class="content-panel">',
            '<div class="section-header">',
            "<div>",
            "<h2>Venue Guide</h2>",
            f"<p id=\"result-count\">{upcoming_production_count} upcoming productions across {len([t for t in theater_map if grouped.get(t)])} venues.</p>",
            "</div>",
            "</div>",
            f'<script id="allShowDates" type="application/json">{all_show_dates_json}</script>',
            filter_html,
            f'<div class="venue-grid" id="venueGrid">{"".join(venue_cards)}</div>',
            "</section>",
        ]
    )
    return _page_shell(
        title="NYC Small Theater Guide",
        eyebrow="Live Aggregation",
        subtitle=(
            f"{upcoming_instance_count} upcoming performances collected from neighborhood venues. "
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

    return f"""<div class="filter-container active" id="filterContainer">
  <button class="filter-toggle-btn open" id="filterToggle">
    <span>✦ Filter by Date &amp; Venue</span>
    <span class="arrow">▼</span>
  </button>

  <div class="filter-controls">
    <div class="filter-group">
      <label>Date</label>
      <div class="cal-presets" id="calPresets">
        <button type="button" class="cal-preset" data-preset="today">Today</button>
        <button type="button" class="cal-preset" data-preset="weekend">This Weekend</button>
        <button type="button" class="cal-preset" data-preset="this-week">This Week</button>
        <button type="button" class="cal-preset" data-preset="next-week">Next Week</button>
      </div>
      <div id="calendarContainer"></div>
      <div class="cal-legend">
        <span class="cal-legend-item"><span class="cal-dot cal-dot-show"></span> Has shows</span>
        <span class="cal-legend-item"><span class="cal-dot"></span> Selected</span>
      </div>
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
      <button class="filter-reset" id="filterReset">Reset Filters</button>
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
  // --- Filter state ---
  const filterState = { venues: new Set() };
  const selectedDates = new Set();
  let calYear, calMonth;
  let anchorDate = null;   // last-clicked date, used for shift+click range fill

  // All dates that have any show — loaded from embedded JSON (covers every
  // production instance, not just the preview rows shown on this page)
  const showDates = new Set(
    JSON.parse(document.getElementById('allShowDates').textContent)
  );

  const filterContainer     = document.getElementById('filterContainer');
  const filterToggle        = document.getElementById('filterToggle');
  const filterReset         = document.getElementById('filterReset');
  const venueSelect         = document.getElementById('venueSelect');
  const venueSelectDropdown = document.getElementById('venueSelectDropdown');
  const venueSelectText     = document.getElementById('venueSelectText');
  const venueCheckboxes     = document.querySelectorAll('.venue-checkbox');
  const venueGrid           = document.getElementById('venueGrid');
  const resultCount         = document.getElementById('result-count');
  const initialResultText   = resultCount.textContent;

  // --- Calendar ---
  const MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
  const DAYS   = ['Mo','Tu','We','Th','Fr','Sa','Su'];

  function pad2(n) { return String(n).padStart(2, '0'); }
  function toDateStr(y, m, d) { return y + '-' + pad2(m + 1) + '-' + pad2(d); }

  // Fill every date between a and b (inclusive) into selectedDates.
  // Iterates by calendar day (not by 86_400_000 ms) so DST transitions
  // like spring-forward don't drop the final date.
  function fillRange(a, b) {
    const parse = function(s) {
      const p = s.split('-');
      return new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
    };
    let lo = parse(a), hi = parse(b);
    if (lo > hi) { const tmp = lo; lo = hi; hi = tmp; }
    const cur = new Date(lo.getFullYear(), lo.getMonth(), lo.getDate());
    while (cur <= hi) {
      selectedDates.add(toDateStr(cur.getFullYear(), cur.getMonth(), cur.getDate()));
      cur.setDate(cur.getDate() + 1);
    }
    anchorDate = b;
  }

  function renderCalendar(year, month) {
    calYear = year; calMonth = month;
    const container = document.getElementById('calendarContainer');

    const today    = new Date();
    const todayStr = toDateStr(today.getFullYear(), today.getMonth(), today.getDate());

    // Monday-first offset (0=Mon … 6=Sun)
    const firstDow    = new Date(year, month, 1).getDay();
    const startOffset = firstDow === 0 ? 6 : firstDow - 1;
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrev  = new Date(year, month, 0).getDate();

    const dayHeaders = DAYS.map(function(d) { return '<th>' + d + '</th>'; }).join('');
    let cells = [], rows = [];

    // Previous-month overflow — not interactive
    for (let i = 0; i < startOffset; i++) {
      cells.push('<td class="cal-day other-month">' + (daysInPrev - startOffset + 1 + i) + '</td>');
    }

    // Current-month cells — ALL are clickable; data-date always present
    for (let d = 1; d <= daysInMonth; d++) {
      const ds  = toDateStr(year, month, d);
      const cls = ['cal-day'];
      if (showDates.has(ds))     cls.push('has-show');
      if (selectedDates.has(ds)) cls.push('selected');
      if (ds === todayStr)        cls.push('today');
      cells.push('<td class="' + cls.join(' ') + '" data-date="' + ds + '">' + d + '</td>');
      if (cells.length === 7) { rows.push('<tr>' + cells.join('') + '</tr>'); cells = []; }
    }

    // Next-month overflow — not interactive
    let nextDay = 1;
    while (cells.length > 0 && cells.length < 7) {
      cells.push('<td class="cal-day other-month">' + (nextDay++) + '</td>');
    }
    if (cells.length) rows.push('<tr>' + cells.join('') + '</tr>');

    container.innerHTML =
      '<div class="cal-header">' +
        '<button class="cal-nav" id="calPrev">&#8249;</button>' +
        '<span>' + MONTHS[month] + ' ' + year + '</span>' +
        '<button class="cal-nav" id="calNext">&#8250;</button>' +
      '</div>' +
      '<table class="cal-table">' +
        '<thead><tr>' + dayHeaders + '</tr></thead>' +
        '<tbody>' + rows.join('') + '</tbody>' +
      '</table>';

    document.getElementById('calPrev').onclick = function() {
      let m = month - 1, y = year;
      if (m < 0) { m = 11; y--; }
      renderCalendar(y, m);
    };
    document.getElementById('calNext').onclick = function() {
      let m = month + 1, y = year;
      if (m > 11) { m = 0; y++; }
      renderCalendar(y, m);
    };

    // Every current-month cell is clickable.
    // Shift+click fills the range from the last anchor to the clicked date.
    container.querySelectorAll('.cal-day:not(.other-month)').forEach(function(cell) {
      cell.onclick = function(e) {
        const ds = cell.getAttribute('data-date');
        if (e.shiftKey && anchorDate && anchorDate !== ds) {
          fillRange(anchorDate, ds);
        } else if (selectedDates.has(ds)) {
          selectedDates.delete(ds);
          anchorDate = null;
        } else {
          selectedDates.add(ds);
          anchorDate = ds;
        }
        renderCalendar(calYear, calMonth);
        applyFilters();
      };
    });
  }

  // Initialise calendar to the current month
  (function() {
    const now = new Date();
    renderCalendar(now.getFullYear(), now.getMonth());
  })();

  // --- Date preset buttons (Today / This Weekend / This Week / Next Week) ---
  // Weeks run Monday-Sunday to match the calendar grid.
  function startOfWeekMonday(d) {
    const dow = d.getDay();                   // 0=Sun..6=Sat
    const offset = dow === 0 ? -6 : 1 - dow;  // back up to Monday
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() + offset);
  }
  function applyPreset(name) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let startDate, endDate;
    if (name === 'today') {
      startDate = endDate = today;
    } else if (name === 'weekend') {
      // Fri/Sat/Sun of the current week. If it's already past Sunday
      // (it can't be — Sun is day 0) or we're on a weekday, pick the
      // upcoming Fri..Sun. If today is Fri/Sat/Sun, start from today.
      const dow = today.getDay();             // 0=Sun..6=Sat
      if (dow === 0) {                        // Sunday → just today
        startDate = endDate = today;
      } else if (dow === 6) {                 // Saturday → Sat+Sun
        startDate = today;
        endDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
      } else {                                // Mon-Fri → upcoming Fri..Sun
        const daysToFri = 5 - dow;
        startDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() + daysToFri);
        endDate   = new Date(today.getFullYear(), today.getMonth(), today.getDate() + daysToFri + 2);
      }
    } else if (name === 'this-week') {
      startDate = startOfWeekMonday(today);
      endDate   = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + 6);
      // Never include past days — clamp the start to today if needed.
      if (startDate < today) startDate = today;
    } else if (name === 'next-week') {
      const thisMon = startOfWeekMonday(today);
      startDate = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + 7);
      endDate   = new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + 13);
    } else {
      return;
    }
    // Replace any existing selection so the preset behaves as a shortcut,
    // not an additive toggle.
    selectedDates.clear();
    const startStr = toDateStr(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
    const endStr   = toDateStr(endDate.getFullYear(),   endDate.getMonth(),   endDate.getDate());
    fillRange(startStr, endStr);
    // Jump the calendar to the month containing the first selected day
    // so users can see what they picked.
    renderCalendar(startDate.getFullYear(), startDate.getMonth());
    applyFilters();
  }
  document.querySelectorAll('.cal-preset').forEach(function(btn) {
    btn.addEventListener('click', function() {
      applyPreset(btn.getAttribute('data-preset'));
    });
  });

  // --- Filter-panel toggle ---
  filterToggle.addEventListener('click', function() {
    filterContainer.classList.toggle('active');
    filterToggle.classList.toggle('open');
  });

  // --- Venue dropdown ---
  venueSelect.addEventListener('click', function(e) {
    e.stopPropagation();
    venueSelectDropdown.classList.toggle('open');
    venueSelect.classList.toggle('active');
  });
  document.addEventListener('click', function(e) {
    if (!venueSelect.contains(e.target) && !venueSelectDropdown.contains(e.target)) {
      venueSelectDropdown.classList.remove('open');
      venueSelect.classList.remove('active');
    }
  });

  // --- Venue checkboxes — live filtering ---
  const totalVenueCount = [...venueCheckboxes].filter(function(cb) { return cb.value !== 'all'; }).length;

  venueCheckboxes.forEach(function(cb) {
    cb.addEventListener('change', function() {
      if (cb.value === 'all') {
        [...venueCheckboxes].forEach(function(c) {
          if (c.value !== 'all') {
            c.checked = cb.checked;
            if (cb.checked) filterState.venues.add(c.value);
            else filterState.venues.delete(c.value);
          }
        });
      } else {
        if (cb.checked) filterState.venues.add(cb.value);
        else filterState.venues.delete(cb.value);
      }
      updateVenueSelectText();
      applyFilters();
    });
  });

  function updateVenueSelectText() {
    const n = filterState.venues.size;
    if (n === 0 || n === totalVenueCount) {
      venueSelectText.textContent = 'All Venues';
    } else if (n === 1) {
      const id = [...filterState.venues][0];
      venueSelectText.textContent = id.replace(/_/g, ' ').replace(/\\b\\w/g, function(l) { return l.toUpperCase(); });
    } else {
      venueSelectText.textContent = n + ' venues selected';
    }
  }

  // --- Core filter logic (runs immediately on every state change) ---
  function applyFilters() {
    let visibleCount = 0;

    document.querySelectorAll('.venue-card').forEach(function(card) {
      const venue        = card.getAttribute('data-venue');
      const isVenueMatch = filterState.venues.size === 0 || filterState.venues.has(venue);

      const rows = card.querySelectorAll('.show-preview-row');
      let hasVisibleRow  = selectedDates.size === 0;

      rows.forEach(function(row) {
        const dateItems = row.querySelectorAll('.show-preview-date');
        if (selectedDates.size === 0) {
          row.style.display = 'flex';
          row.classList.remove('date-filtered');
          // Restore every <li> so the list is clean if filter is reactivated.
          dateItems.forEach(function(li) { li.classList.remove('hidden'); });
        } else {
          // data-all-dates contains every performance date for this production;
          // fall back to data-show-date for backward compatibility
          const raw = row.getAttribute('data-all-dates') || row.getAttribute('data-show-date') || '';
          const visible = raw.split(',').some(function(d) { return d && selectedDates.has(d); });
          row.style.display = visible ? 'flex' : 'none';
          if (visible) {
            hasVisibleRow = true;
            row.classList.add('date-filtered');
            // Show only the performance dates that intersect the current selection.
            dateItems.forEach(function(li) {
              const d = li.getAttribute('data-date');
              li.classList.toggle('hidden', !selectedDates.has(d));
            });
          } else {
            row.classList.remove('date-filtered');
          }
        }
      });

      const shouldShow = isVenueMatch && hasVisibleRow;
      card.classList.toggle('hidden', !shouldShow);
      if (shouldShow) visibleCount++;
    });

    updateResultCount(visibleCount);
  }

  // --- Reset ---
  filterReset.addEventListener('click', function() {
    selectedDates.clear();
    anchorDate = null;
    filterState.venues.clear();
    [...venueCheckboxes].forEach(function(cb) { cb.checked = false; });
    updateVenueSelectText();
    renderCalendar(calYear, calMonth);
    venueGrid.querySelectorAll('.venue-card').forEach(function(card) {
      card.classList.remove('hidden');
      card.querySelectorAll('.show-preview-row').forEach(function(row) {
        row.style.display = 'flex';
        row.classList.remove('date-filtered');
        row.querySelectorAll('.show-preview-date.hidden').forEach(function(li) {
          li.classList.remove('hidden');
        });
      });
    });
    resultCount.textContent = initialResultText;
  });

  function updateResultCount(count) {
    const total = venueGrid.querySelectorAll('.venue-card').length;
    resultCount.textContent = count === total
      ? initialResultText
      : count + ' of ' + total + ' venues shown.';
  }
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
