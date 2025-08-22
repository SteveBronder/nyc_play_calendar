from __future__ import annotations

"""Google Calendar API integration."""

from typing import Dict

try:  # pragma: no cover - optional dependency for tests
    from googleapiclient.errors import HttpError  # type: ignore
except Exception:  # pragma: no cover - used when library missing
    class HttpError(Exception):
        def __init__(self, resp, content):  # minimal stub for tests
            self.resp = resp
            super().__init__(str(content))

from .models import EventInstance


class GoogleCalendarClient:
    """Minimal client wrapping Google Calendar API calls.

    The class expects an already authorized ``service`` object from
    ``googleapiclient.discovery.build``.  In tests this service can be mocked to
    validate behaviour without performing network requests.
    """

    def __init__(self, service, calendar_id: str = "primary") -> None:
        self.service = service
        self.calendar_id = calendar_id

    def _event_body(self, event: EventInstance) -> Dict:
        location = f"{event.venue_name} – {event.venue_address}" if event.venue_address else event.venue_name
        return {
            "id": event.uid,
            "summary": event.title,
            "description": f"{event.description}\nPrice: {event.price}",
            "start": {"dateTime": event.start.isoformat(), "timeZone": str(event.start.tzinfo)},
            "end": {"dateTime": event.end.isoformat(), "timeZone": str(event.end.tzinfo)},
            "location": location,
        }

    def upsert_event(self, event: EventInstance) -> str:
        """Insert or update ``event`` on Google Calendar.

        Returns ``"inserted"`` or ``"updated"`` depending on the performed
        action.
        """

        body = self._event_body(event)
        try:
            self.service.events().insert(calendarId=self.calendar_id, body=body).execute()
            return "inserted"
        except HttpError as exc:  # duplicate -> update
            if getattr(exc.resp, "status", None) == 409:
                self.service.events().update(calendarId=self.calendar_id, eventId=event.uid, body=body).execute()
                return "updated"
            raise
