from nyc_events_etl.scrapers import frigid, public_theater

FRIGID_HTML = """
<div class="event">
  <span class="title">Measure for Measure</span>
  <span class="desc">A play.</span>
  <span class="date">Aug 16</span>
  <span class="time">7 pm</span>
  <span class="price">$20</span>
  <span class="venue">Under St Marks</span>
  <span class="address">94 St Marks Pl</span>
</div>
"""

PUBLIC_HTML = """
<div class="event">
  <span class="title">Pericles</span>
  <span class="desc">Concert</span>
  <span class="date">Aug 29</span>
  <span class="time">8 pm</span>
  <span class="price">Free</span>
  <span class="venue">Cathedral</span>
  <span class="address">112 St</span>
</div>
"""


def test_frigid_scraper():
    events = frigid.parse_html(FRIGID_HTML, 2025)
    assert events[0].title == "Measure for Measure"
    assert events[0].dates[0].day == 16


def test_public_theater_scraper():
    events = public_theater.parse_html(PUBLIC_HTML, 2025)
    assert events[0].venue_name == "Cathedral"
    assert events[0].start_times[0].hour == 20
