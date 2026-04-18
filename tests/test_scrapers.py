import json
from datetime import date, time

from nyc_events_etl.scrapers import caveat, frigid, public_theater

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


CAVEAT_API_JSON = json.dumps({
    "records": [
        {
            "id": "rec123",
            "fields": {
                "Event": "Comedy Night Live",
                "datestring": "2026-05-10",
                "Event start TIME ONLY": "8:00 PM",
                "Doors TIME ONLY": "7:30 PM",
                "description": "A hilarious evening of stand-up comedy.",
                "Short description": "Stand-up comedy night",
                "Ticket URL": "https://www.caveat.nyc/event/comedy-night-live-5-10-2026",
                "slug": "comedy-night-live-5-10-2026",
                "Tickets advance": 15,
                "Tickets door": 20,
                "Tickets Livestream": 10,
                "Tags": "Comedy",
                "Livestream": True,
            },
        },
        {
            "id": "rec456",
            "fields": {
                "Event": "Sold Out Lecture",
                "datestring": "2026-05-11",
                "Event start TIME ONLY": "7:00 PM",
                "description": "",
                "Short description": "An interesting talk.",
                "Ticket URL": "https://www.caveat.nyc/event/sold-out-lecture-5-11-2026",
                "slug": "sold-out-lecture-5-11-2026",
                "Tickets advance": 25,
                "Sold out": True,
            },
        },
        {
            "id": "rec789",
            "fields": {
                "Event": "",
                "datestring": "2026-05-12",
                "Event start TIME ONLY": "9:00 PM",
            },
        },
        {
            "id": "rec000",
            "fields": {
                "Event": "No Date Event",
                "Event start TIME ONLY": "9:00 PM",
            },
        },
    ]
})


def test_caveat_parse_api_response():
    events = caveat.parse_api_response(CAVEAT_API_JSON)

    # Should skip the record with empty title and the one with no date
    assert len(events) == 2

    # First event: normal event with pricing
    e1 = events[0]
    assert e1["title"] == "Comedy Night Live"
    assert e1["date"] == date(2026, 5, 10)
    assert e1["start_time"] == time(20, 0)
    assert "$15 advance" in e1["price"]
    assert "$20 door" in e1["price"]
    assert "$10 livestream" in e1["price"]
    assert e1["description"] == "A hilarious evening of stand-up comedy."
    assert e1["ticket_url"] == "https://www.caveat.nyc/event/comedy-night-live-5-10-2026"

    # Second event: sold out, uses short description as fallback
    e2 = events[1]
    assert e2["title"] == "Sold Out Lecture"
    assert e2["date"] == date(2026, 5, 11)
    assert e2["start_time"] == time(19, 0)
    assert "SOLD OUT" in e2["price"]
    assert "$25 advance" in e2["price"]
    assert e2["description"] == "An interesting talk."


def test_caveat_build_price_text():
    # All prices
    fields = {"Tickets advance": 15, "Tickets door": 20, "Tickets Livestream": 10, "Tickets Premium": 25}
    assert caveat._build_price_text(fields) == "$15 advance, $20 door, $25 premium, $10 livestream"

    # Only advance
    fields = {"Tickets advance": 15}
    assert caveat._build_price_text(fields) == "$15 advance"

    # Door same as advance (should not duplicate)
    fields = {"Tickets advance": 15, "Tickets door": 15}
    assert caveat._build_price_text(fields) == "$15 advance"

    # Empty
    assert caveat._build_price_text({}) == ""


def test_caveat_parse_time():
    assert caveat._parse_time("7:00 PM") == time(19, 0)
    assert caveat._parse_time("12:30 AM") == time(0, 30)
    assert caveat._parse_time(None) is None
    assert caveat._parse_time("") is None


def test_caveat_parse_date():
    assert caveat._parse_date("2026-04-18") == date(2026, 4, 18)
    assert caveat._parse_date(None) is None
    assert caveat._parse_date("") is None
