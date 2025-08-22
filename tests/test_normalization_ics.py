from datetime import date, time
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
        source="http://example.com/rock",
    )
    events = expand_series(series)
    assert len(events) == 2
    assert "Source: http://example.com/rock" in events[0].description
    ics_bytes = events_to_ics(events)
    text = ics_bytes.decode()
    assert text.count("BEGIN:VEVENT") == 2
    assert "SUMMARY:Rock Show" in text
    assert "DTSTART;TZID=America/New_York" in text
    assert "Source: http://example.com/rock" in text
