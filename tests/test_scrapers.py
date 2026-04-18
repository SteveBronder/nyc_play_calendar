from datetime import date, time

from nyc_events_etl.scrapers import frigid, public_theater
from nyc_events_etl.scrapers.slipper_room import _parse_wix_datetime, _strip_date_suffix

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


def test_slipper_room_parse_wix_datetime():
    result = _parse_wix_datetime("Apr 18, 2026, 8:00 PM")
    assert result == (date(2026, 4, 18), time(20, 0))

    result = _parse_wix_datetime("May 3, 2026, 5:00 PM")
    assert result == (date(2026, 5, 3), time(17, 0))

    result = _parse_wix_datetime("Dec 31, 2026, 10:45 PM")
    assert result == (date(2026, 12, 31), time(22, 45))

    result = _parse_wix_datetime("no date here")
    assert result is None


def test_slipper_room_parse_wix_datetime_in_context():
    # Datetime embedded in longer text (as it appears in the detail card)
    text = "Some title Apr 18, 2026, 8:00 PM New York, 167 Orchard St"
    result = _parse_wix_datetime(text)
    assert result == (date(2026, 4, 18), time(20, 0))


def test_slipper_room_strip_date_suffix():
    # Period before month name
    assert _strip_date_suffix("Mr. Choade's Upstairs Downstairs. April 18") == "Mr. Choade's Upstairs Downstairs"
    assert _strip_date_suffix("Guest Event: Visceral Abstractions. April 20") == "Guest Event: Visceral Abstractions"
    assert _strip_date_suffix("Slippery Sundays. May 10") == "Slippery Sundays"
    # No period before month name (space only)
    assert _strip_date_suffix("The Slipper Room Show! May 1") == "The Slipper Room Show!"
    assert _strip_date_suffix("The Glitter Gutter!!! April 22") == "The Glitter Gutter!!!"
    assert _strip_date_suffix("Slipper Room Midnight Show. April 18") == "Slipper Room Midnight Show"
    # No date suffix at all
    assert _strip_date_suffix("A Simple Title") == "A Simple Title"
