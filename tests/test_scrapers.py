from unittest.mock import Mock, patch

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


def test_frigid_fetch_events_sleeps():
    session = Mock()
    resp = Mock()
    resp.text = FRIGID_HTML
    resp.raise_for_status = Mock()
    session.get.return_value = resp
    with patch("nyc_events_etl.scrapers.frigid.time.sleep") as sleep_mock:
        events = frigid.fetch_events(session=session, sleep_secs=1.5)
        assert events[0].title == "Measure for Measure"
        sleep_mock.assert_called_once_with(1.5)


def test_public_fetch_events_sleeps():
    session = Mock()
    resp = Mock()
    resp.text = PUBLIC_HTML
    resp.raise_for_status = Mock()
    session.get.return_value = resp
    with patch("nyc_events_etl.scrapers.public_theater.time.sleep") as sleep_mock:
        events = public_theater.fetch_events(session=session, sleep_secs=1.25)
        assert events[0].venue_name == "Cathedral"
        sleep_mock.assert_called_once_with(1.25)
