from datetime import date, time

from nyc_events_etl.schedule import (
    collect_body_lines,
    expand_weekly_schedule,
    parse_performance_space_schedule_lines,
    parse_nytw_ticket_calendar,
    parse_vineyard_schedule_lines,
)
from nyc_events_etl.scrapers.common import parse_ticketmaster_events_from_html


def test_parse_vineyard_schedule_lines():
    lines = [
        "Tuesday",
        "May 12, 2026 | 7:00 PM",
        "$20 First Preview",
        "BOOK NOW",
        "Sunday",
        "May 17, 2026 | 2:00 PM",
    ]
    parsed = parse_vineyard_schedule_lines(lines)
    assert parsed == [
        (date(2026, 5, 12), time(19, 0)),
        (date(2026, 5, 17), time(14, 0)),
    ]


def test_parse_nytw_ticket_calendar():
    lines = [
        "APRIL 2026",
        "Sun",
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "29",
        "2pm",
        "30",
        "7pm - $59",
    ]
    parsed = parse_nytw_ticket_calendar(lines)
    assert parsed == [
        (date(2026, 4, 29), time(14, 0)),
        (date(2026, 4, 30), time(19, 0)),
    ]


def test_expand_weekly_schedule():
    parsed = expand_weekly_schedule(
        "APR 2 - APR 12",
        "THU, FRI, SAT at 8 PM, SUN at 3 PM",
        default_year=2026,
    )
    assert parsed[0] == (date(2026, 4, 2), time(20, 0))
    assert parsed[-1] == (date(2026, 4, 12), time(15, 0))
    assert len(parsed) == 8


def test_parse_performance_space_schedule_lines():
    lines = [
        "October 17th (click to see schedule):",
        "6:00PM",
        "Podcast 1",
        "8:30PM",
        "October 18th (click to see schedule):",
        "3PM",
        "Sun, March 1, 2026 | 7pm— WIP FEEDBACK FRONT,",
        "Dec 6 | 1pm",
    ]
    parsed = parse_performance_space_schedule_lines(lines, reference_date=date(2026, 4, 8))
    assert parsed == [
        (date(2025, 10, 17), time(18, 0)),
        (date(2025, 10, 17), time(20, 30)),
        (date(2025, 10, 18), time(15, 0)),
        (date(2026, 3, 1), time(19, 0)),
        (date(2025, 12, 6), time(13, 0)),
    ]


def test_parse_ticketmaster_events_from_html():
    html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "eventsJsonLD": [[
                {
                  "@type": "Event",
                  "name": "Burnout Paradise",
                  "startDate": "2026-04-09T14:00:00",
                  "eventStatus": "https://schema.org/EventScheduled",
                  "url": "https://www.ticketmaster.com/event/1",
                  "location": {
                    "name": "Astor Place Theatre",
                    "address": {
                      "streetAddress": "434 Lafayette Street",
                      "addressLocality": "New York",
                      "addressRegion": "NY",
                      "postalCode": "10003"
                    }
                  },
                  "offers": {
                    "url": "https://www.ticketmaster.com/event/1"
                  }
                },
                {
                  "@type": "Event",
                  "name": "Cancelled Event",
                  "startDate": "2026-04-10T14:00:00",
                  "eventStatus": "https://schema.org/EventCancelled"
                }
              ]]
            }
          }
        }
      </script>
    </body></html>
    """
    parsed = parse_ticketmaster_events_from_html(html)
    assert parsed == [
        {
            "title": "Burnout Paradise",
            "date": date(2026, 4, 9),
            "time": time(14, 0),
            "event_url": "https://www.ticketmaster.com/event/1",
            "venue_name": "Astor Place Theatre",
            "venue_address": "434 Lafayette Street, New York, NY, 10003",
        }
    ]
