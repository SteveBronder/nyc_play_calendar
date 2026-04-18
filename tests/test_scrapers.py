from datetime import date, time

from nyc_events_etl.scrapers import frigid, public_theater
from nyc_events_etl.scrapers.asylum import extract_events_list, format_price, parse_api_events, strip_html

FRIGID_HTML = """
<div class="event">
  <span class="title">Measure for Measure</span>
  <a href="https://frigid.example/measure">Details</a>
  <span class="date">Aug 16</span>
  <span class="time">7 pm</span>
  <span class="venue">Under St Marks</span>
  <span class="address">94 St Marks Pl</span>
</div>
"""

PUBLIC_HTML = """
<div class="event">
  <span class="title">Pericles</span>
  <span class="desc">Concert</span>
  <a href="https://public.example/pericles">Info</a>
  <span class="date">Aug 29</span>
  <span class="time">8 pm</span>
  <span class="venue">Cathedral</span>
  <span class="address">112 St</span>
</div>
"""


def test_frigid_scraper():
    def fake_fetch(url: str) -> str:
        assert url == "https://frigid.example/measure"
        return "<span class=\"desc\">A play.</span><span class=\"price\">$20</span>"

    events = frigid.parse_html(FRIGID_HTML, 2025, fetch=fake_fetch)
    event = events[0]
    assert event.title == "Measure for Measure"
    assert event.dates[0].day == 16
    assert event.description == "A play."
    assert event.price == "$20"
    assert event.source == "https://frigid.example/measure"


def test_public_theater_scraper():
    def fake_fetch(url: str) -> str:
        assert url == "https://public.example/pericles"
        return "<span class=\"price\">Free</span>"

    events = public_theater.parse_html(PUBLIC_HTML, 2025, fetch=fake_fetch)
    event = events[0]
    assert event.venue_name == "Cathedral"
    assert event.start_times[0].hour == 20
    assert event.price == "Free"
    assert event.source == "https://public.example/pericles"


ASYLUM_API_JSON = [
    {
        "id": "924c9a80-1f38-4b23-90e2-557af56746e9",
        "title": "Shitzprobe",
        "description": "<h4>A wild comedy show</h4><p>Hosted by <b>comics</b>.</p>",
        "start": "2026-04-20T23:00:00.000Z",
        "end": "2026-04-21T00:30:00.000Z",
        "imageUrl": "https://static.tixr.com/img1.jpg",
        "price": 30,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175311",
        "status": "available",
        "sales": [
            {"id": 1956494, "name": "General Admission", "currentPrice": 30, "state": "OPEN"},
        ],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
    {
        "id": "aaa11111-2222-3333-4444-555566667777",
        "title": "Shitzprobe",
        "description": "<h4>A wild comedy show</h4><p>Hosted by <b>comics</b>.</p>",
        "start": "2026-05-04T23:00:00.000Z",
        "end": "2026-05-05T00:30:00.000Z",
        "imageUrl": "https://static.tixr.com/img2.jpg",
        "price": 30,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175312",
        "status": "available",
        "sales": [],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
    {
        "id": "bbb22222-3333-4444-5555-666677778888",
        "title": "Chris Hall",
        "description": "<p>An evening of magic.</p>",
        "start": "2026-04-22T23:30:00.000Z",
        "end": "2026-04-23T01:00:00.000Z",
        "imageUrl": "https://static.tixr.com/img3.jpg",
        "price": 25,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/chris-hall-123",
        "status": "available",
        "sales": [],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
]


def test_asylum_strip_html():
    assert strip_html("<h4>Hello</h4><p>World</p>") == "Hello World"
    assert strip_html("") == ""
    assert strip_html("plain text") == "plain text"
    assert strip_html("<b>bold</b> and <i>italic</i>") == "bold and italic"


def test_asylum_format_price():
    assert format_price(30) == "$30"
    assert format_price(25.50) == "$25.50"
    assert format_price(0) == "Free"
    assert format_price(None) == ""
    assert format_price("invalid") == ""


def test_asylum_parse_api_events():
    bundle = parse_api_events(ASYLUM_API_JSON)

    # Should group by title: 2 Shitzprobe events -> 1 production, Chris Hall -> 1 production
    assert len(bundle.productions) == 2
    titles = {p.title for p in bundle.productions}
    assert titles == {"Shitzprobe", "Chris Hall"}

    # Should have 3 series total (one per event instance)
    assert len(bundle.series) == 3

    # Verify UTC -> ET conversion for first Shitzprobe event
    # 2026-04-20T23:00:00Z = 2026-04-20 19:00 ET (EDT, UTC-4)
    shitz_series = [s for s in bundle.series if s.title == "Shitzprobe"]
    assert len(shitz_series) == 2
    first = shitz_series[0]
    assert first.dates == [date(2026, 4, 20)]
    assert first.start_times == [time(19, 0)]
    assert first.end_time == time(20, 30)

    # Verify Chris Hall UTC -> ET conversion
    # 2026-04-22T23:30:00Z = 2026-04-22 19:30 ET (EDT, UTC-4)
    chris_series = [s for s in bundle.series if s.title == "Chris Hall"]
    assert len(chris_series) == 1
    assert chris_series[0].dates == [date(2026, 4, 22)]
    assert chris_series[0].start_times == [time(19, 30)]
    assert chris_series[0].end_time == time(21, 0)


def test_asylum_production_metadata():
    bundle = parse_api_events(ASYLUM_API_JSON)

    shitz_prod = [p for p in bundle.productions if p.title == "Shitzprobe"][0]
    assert shitz_prod.theater_id == "asylum"
    assert shitz_prod.theater_name == "Asylum NYC"
    assert shitz_prod.venue_name == "Asylum NYC"
    assert shitz_prod.venue_address == "123 E 24th St, New York, NY 10010"
    assert shitz_prod.price == "$30"
    assert shitz_prod.schedule_granularity == "instance"
    assert "wild comedy show" in shitz_prod.description
    assert "<" not in shitz_prod.description  # HTML tags stripped
    assert shitz_prod.ticket_url == "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175311"


def test_asylum_empty_api():
    bundle = parse_api_events([])
    assert len(bundle.productions) == 0
    assert len(bundle.series) == 0


def test_asylum_extract_events_list():
    # Plain list format
    events = [{"title": "A"}]
    assert extract_events_list(events) == [{"title": "A"}]

    # Dict with "events" key (actual API format)
    wrapped = {"events": [{"title": "B"}], "total": 1, "timezone": "America/New_York"}
    assert extract_events_list(wrapped) == [{"title": "B"}]

    # Unrecognized format
    assert extract_events_list("bad") is None
    assert extract_events_list({"no_events_key": True}) is None
