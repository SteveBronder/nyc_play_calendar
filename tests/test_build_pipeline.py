from datetime import date, datetime, time
from pathlib import Path

from nyc_events_etl.build import load_artifact, render_site, write_artifact
from nyc_events_etl.models import EventInstance, TheaterProduction


def make_production() -> TheaterProduction:
    return TheaterProduction(
        production_id="prod-1",
        theater_id="vineyard",
        theater_name="Vineyard Theatre",
        title="Girls Chance Music",
        description="A test production.",
        venue_name="Vineyard Theatre",
        source_url="https://example.com/show",
        ticket_url="https://tickets.example.com/show",
        run_range_text="May 12 - Jun 21, 2026",
    )


def make_instance() -> EventInstance:
    return EventInstance(
        uid="evt-1",
        title="Girls Chance Music",
        description="A test production.",
        price="$45",
        venue_name="Vineyard Theatre",
        venue_address="108 E 15th St",
        start=datetime(2026, 5, 12, 19, 0),
        end=datetime(2026, 5, 12, 20, 50),
        theater_id="vineyard",
        theater_name="Vineyard Theatre",
        production_id="prod-1",
        source="https://example.com/show",
        ticket_url="https://tickets.example.com/show",
    )


def test_write_artifact_and_render_site(tmp_path: Path):
    artifact_path = tmp_path / "data" / "events.json"
    site_dir = tmp_path / "site"
    payload = write_artifact([make_production()], [make_instance()], artifact_path)
    assert payload["production_count"] == 1
    assert payload["instance_count"] == 1

    loaded = load_artifact(artifact_path)
    render_site(loaded, site_dir)

    index_html = (site_dir / "index.html").read_text()
    theater_html = (site_dir / "theaters" / "vineyard.html").read_text()
    assert "Girls Chance Music" in index_html
    assert "View venue" in index_html
    assert "Back to all theaters" in theater_html
    assert "Upcoming Dates" in theater_html
    assert "Tickets" in theater_html
