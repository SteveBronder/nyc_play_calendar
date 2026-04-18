from nyc_events_etl.scrapers import frigid, public_theater

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


def test_public_theater_parse_calendar_datetime():
    from datetime import date, time
    from nyc_events_etl.scrapers.public_theater import _parse_calendar_datetime

    result = _parse_calendar_datetime("Fri, April 17 | 7:00PM", 2026)
    assert result is not None
    assert result[0] == date(2026, 4, 17)
    assert result[1] == time(19, 0)

    result2 = _parse_calendar_datetime("Sat, January 10 | 1:00PM", 2027)
    assert result2 is not None
    assert result2[0] == date(2027, 1, 10)
    assert result2[1] == time(13, 0)

    assert _parse_calendar_datetime("No date here", 2026) is None
