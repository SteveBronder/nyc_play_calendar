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
