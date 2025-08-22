from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from nyc_events_etl.google_calendar import GoogleCalendarClient, HttpError
from nyc_events_etl.models import EventInstance


def make_event():
    start = datetime(2025, 8, 3, 16, 0)
    end = start + timedelta(hours=1)
    return EventInstance(
        uid="uid1",
        title="Rock Show",
        description="Loud music",
        price="$10",
        venue_name="Rockbar",
        venue_address="123 St",
        start=start,
        end=end,
        all_day=False,
    )


def test_insert(monkeypatch):
    service = MagicMock()
    gc = GoogleCalendarClient(service)
    action = gc.upsert_event(make_event())
    assert action == "inserted"
    assert service.events.return_value.insert.called


def test_update_on_conflict(monkeypatch):
    service = MagicMock()
    insert = service.events.return_value.insert.return_value
    insert.execute.side_effect = HttpError(
        resp=SimpleNamespace(status=409), content=b""
    )
    gc = GoogleCalendarClient(service)
    action = gc.upsert_event(make_event())
    assert action == "updated"
    assert service.events.return_value.update.called


def test_all_day_event_body():
    start = datetime(2025, 8, 3)
    end = start + timedelta(days=1)
    event = EventInstance(
        uid="uid2",
        title="Holiday",
        description="All day fun",
        price="Free",
        venue_name="City",
        venue_address="",
        start=start,
        end=end,
        all_day=True,
    )
    gc = GoogleCalendarClient(MagicMock())
    body = gc._event_body(event)
    assert body["start"] == {"date": "2025-08-03"}
    assert body["end"] == {"date": "2025-08-04"}
