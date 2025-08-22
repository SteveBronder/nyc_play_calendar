from datetime import datetime
from nyc_events_etl.models import EventSeries, expand_series


def test_expand_series_yields_instances():
    dt = datetime(2025, 8, 3)
    series = EventSeries(title="Test", datetimes=[dt])
    instances = list(expand_series(series))
    assert len(instances) == 1
    inst = instances[0]
    assert inst.title == "Test"
    assert inst.start == dt
    assert inst.end == dt
