import json
import re
from datetime import datetime
from pathlib import Path

from nyc_events_etl.models import EventSeries
from nyc_events_etl.normalization import expand_series
from nyc_events_etl.google_calendar import GoogleCalendarClient


class DummyEvents:
    def __init__(self, store):
        self.store = store

    def insert(self, calendarId, body):
        self.store.append(body)

        class Exec:
            def execute(self):
                return {}

        return Exec()

    def update(self, calendarId, eventId, body):  # pragma: no cover - not used
        class Exec:
            def execute(self):
                return {}

        return Exec()


class DummyService:
    def __init__(self):
        self.inserted = []

    def events(self):
        return DummyEvents(self.inserted)


def _make_client():
    service = DummyService()
    client = GoogleCalendarClient(service)
    return client, service


def test_frigid_example_flow():
    base = Path(__file__).resolve().parent.parent / "examples" / "frigid"
    main_html = (base / "main_page" / "frigid_main_page.html").read_text()
    # Locate event link on main page
    m = re.search(
        r"The Climate Fables: The Clouds.*?href=\"(https://tickets.frigid.nyc/event/[^\"]+)\"",
        main_html,
        re.S,
    )
    assert m, "event link not found on main page"
    event_url = m.group(1)
    assert event_url.endswith("6897:1231")

    # Parse event page
    event_html = (base / "event_pages" / "climate_fables" / "climate_fables.html").read_text()
    title = re.search(r'<h2 class=\"primary-color\">(.*?)</h2>', event_html).group(1).strip()
    desc_match = re.search(
        r'<p style=\"margin-top: 0px\">\s*(.*?)\s*</p>',
        event_html,
        re.S,
    )
    description = re.sub(r"<.*?>", "", desc_match.group(1))
    description = re.sub(r"\s+", " ", description).strip()

    schedule_block = re.search(r'<ul class=\"schedule\">(.*?)</ul>', event_html, re.S).group(1)
    schedule_items = [
        re.sub(r"<.*?>", "", item).strip() for item in re.findall(r'<li>(.*?)</li>', schedule_block, re.S)
    ]
    price, date_text, _duration, venue, address = schedule_items

    perf_json = re.search(
        r'id=\"event-data\"[^>]*data-performances=\"([^\"]*)\"',
        event_html,
    ).group(1)
    perf_data = json.loads(perf_json.replace("&quot;", '"'))
    date_str = perf_data["dates"][0]
    time_str = perf_data["times"][date_str][0]["performanceTime"].split()[0:2]
    perf_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    perf_time = datetime.strptime(" ".join(time_str), "%I:%M %p").time()

    series = EventSeries(
        title=title,
        description=description,
        price=price,
        venue_name=venue,
        venue_address=address,
        dates=[perf_date],
        start_times=[perf_time],
    )
    instance = expand_series(series)[0]

    client, service = _make_client()
    result = client.upsert_event(instance)
    assert result == "inserted"
    assert service.inserted[0]["summary"] == title


def test_public_theater_example_flow():
    base = Path(__file__).resolve().parent.parent / "examples" / "public_theater"
    main_html = (base / "main_page" / "public_theater_main_page.html").read_text()
    link_match = re.search(
        r'<a[^>]*href=\"(https://publictheater.org/productions/season/[^"]+)\"[^>]*>Pericles: A Public Works Concert Experience</a>',
        main_html,
    )
    assert link_match, "event link not found on main page"
    event_url = link_match.group(1)
    assert "pericles-a-public-works-concert-experience" in event_url

    event_html = (base / "event_pages" / "pericles" / "pericles_event.html").read_text()
    title = re.search(
        r'<h1[^>]*>Pericles: A Public Works Concert Experience</h1>', event_html
    ).group(0)
    title = re.sub(r"<.*?>", "", title).strip()

    desc_match = re.search(r'This season[\u2019\'’]s[^<]+', event_html)
    description = desc_match.group(0).split('"')[0].strip()

    venue = re.search(
        r'Venue <span class=\"fw-bold\">([^<]+)</span>', event_html
    ).group(1)
    address = re.search(
        r'Performances will take place at <strong>The Cathedral of St. John the Divine </strong>at<strong> </strong><a[^>]*>([^<]+)</a>',
        event_html,
    ).group(1)

    events_json = re.search(r'const events = (\[.*?\]);', event_html, re.S).group(1)
    events = json.loads(events_json)
    first = events[0]
    date = datetime.strptime(first["start"], "%Y-%m-%d").date()
    time = datetime.strptime(first["eventTime"], "%I:%M %p").time()

    series = EventSeries(
        title=title,
        description=description,
        price="Free",
        venue_name=venue,
        venue_address=address,
        dates=[date],
        start_times=[time],
    )
    instance = expand_series(series)[0]

    client, service = _make_client()
    result = client.upsert_event(instance)
    assert result == "inserted"
    assert service.inserted[0]["location"].startswith("The Cathedral of St. John")
