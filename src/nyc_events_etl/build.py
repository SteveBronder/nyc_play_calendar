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
  .venue-card {
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
            preview.append(
                "\n".join(
                    [
                        '<div class="show-preview-row">',
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
        venue_cards.append(
            "\n".join(
                [
                    '<article class="venue-card">',
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

    body = "\n".join(
        [
            '<section class="content-panel">',
            '<div class="section-header">',
            "<div>",
            "<h2>Venue Guide</h2>",
            f"<p>{payload['production_count']} productions across {len(theater_map)} venues.</p>",
            "</div>",
            "</div>",
            f'<div class="venue-grid">{"".join(venue_cards)}</div>',
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
