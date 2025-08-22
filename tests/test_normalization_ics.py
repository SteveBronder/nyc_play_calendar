from datetime import date, time, timedelta
from nyc_events_etl.models import EventSeries
from nyc_events_etl.normalization import expand_series
from nyc_events_etl.ics import events_to_ics


def test_expand_and_ics():
    series = EventSeries(
        title="Rock Show",
        description="Loud music",
        price="$10",
        venue_name="Rockbar",
        venue_address="123 St",
        dates=[date(2025, 8, 3)],
        start_times=[time(16, 0), time(18, 0)],
    )
    events = expand_series(series)
    assert len(events) == 2
    ics_bytes = events_to_ics(events)
    text = ics_bytes.decode()
    assert text.count("BEGIN:VEVENT") == 2
    assert "SUMMARY:Rock Show" in text
    assert "DTSTART;TZID=America/New_York" in text


def test_all_day_event():
    series = EventSeries(
        title="Picnic",
        description="Fun in the park",
        price="Free",
        venue_name="Central Park",
        venue_address="",
        dates=[date(2025, 8, 3)],
        start_times=[],
        all_day=True,
    )
    events = expand_series(series)
    assert len(events) == 1
    event = events[0]
    assert event.all_day
    assert event.end - event.start == timedelta(days=1)
    ics_bytes = events_to_ics(events)
    text = ics_bytes.decode()
    assert "DTSTART;VALUE=DATE:20250803" in text
    assert "DTEND;VALUE=DATE:20250804" in text
