import json
from datetime import date, time

from nyc_events_etl.scrapers import caveat, frigid, public_theater
from nyc_events_etl.scrapers.asylum import extract_events_list, format_price, parse_api_events, strip_html
from nyc_events_etl.scrapers.here import parse_here_schedule_lines
from nyc_events_etl.scrapers.slipper_room import _parse_wix_datetime, _strip_date_suffix

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


CAVEAT_API_JSON = json.dumps({
    "records": [
        {
            "id": "rec123",
            "fields": {
                "Event": "Comedy Night Live",
                "datestring": "2026-05-10",
                "Event start TIME ONLY": "8:00 PM",
                "Doors TIME ONLY": "7:30 PM",
                "description": "A hilarious evening of stand-up comedy.",
                "Short description": "Stand-up comedy night",
                "Ticket URL": "https://www.caveat.nyc/event/comedy-night-live-5-10-2026",
                "slug": "comedy-night-live-5-10-2026",
                "Tickets advance": 15,
                "Tickets door": 20,
                "Tickets Livestream": 10,
                "Tags": "Comedy",
                "Livestream": True,
            },
        },
        {
            "id": "rec456",
            "fields": {
                "Event": "Sold Out Lecture",
                "datestring": "2026-05-11",
                "Event start TIME ONLY": "7:00 PM",
                "description": "",
                "Short description": "An interesting talk.",
                "Ticket URL": "https://www.caveat.nyc/event/sold-out-lecture-5-11-2026",
                "slug": "sold-out-lecture-5-11-2026",
                "Tickets advance": 25,
                "Sold out": True,
            },
        },
        {
            "id": "rec789",
            "fields": {
                "Event": "",
                "datestring": "2026-05-12",
                "Event start TIME ONLY": "9:00 PM",
            },
        },
        {
            "id": "rec000",
            "fields": {
                "Event": "No Date Event",
                "Event start TIME ONLY": "9:00 PM",
            },
        },
    ]
})


def test_caveat_parse_api_response():
    events = caveat.parse_api_response(CAVEAT_API_JSON)

    # Should skip the record with empty title and the one with no date
    assert len(events) == 2

    # First event: normal event with pricing
    e1 = events[0]
    assert e1["title"] == "Comedy Night Live"
    assert e1["date"] == date(2026, 5, 10)
    assert e1["start_time"] == time(20, 0)
    assert "$15 advance" in e1["price"]
    assert "$20 door" in e1["price"]
    assert "$10 livestream" in e1["price"]
    assert e1["description"] == "A hilarious evening of stand-up comedy."
    assert e1["ticket_url"] == "https://www.caveat.nyc/event/comedy-night-live-5-10-2026"

    # Second event: sold out, uses short description as fallback
    e2 = events[1]
    assert e2["title"] == "Sold Out Lecture"
    assert e2["date"] == date(2026, 5, 11)
    assert e2["start_time"] == time(19, 0)
    assert "SOLD OUT" in e2["price"]
    assert "$25 advance" in e2["price"]
    assert e2["description"] == "An interesting talk."


def test_caveat_build_price_text():
    # All prices
    fields = {"Tickets advance": 15, "Tickets door": 20, "Tickets Livestream": 10, "Tickets Premium": 25}
    assert caveat._build_price_text(fields) == "$15 advance, $20 door, $25 premium, $10 livestream"

    # Only advance
    fields = {"Tickets advance": 15}
    assert caveat._build_price_text(fields) == "$15 advance"

    # Door same as advance (should not duplicate)
    fields = {"Tickets advance": 15, "Tickets door": 15}
    assert caveat._build_price_text(fields) == "$15 advance"

    # Empty
    assert caveat._build_price_text({}) == ""


def test_caveat_parse_time():
    assert caveat._parse_time("7:00 PM") == time(19, 0)
    assert caveat._parse_time("12:30 AM") == time(0, 30)
    assert caveat._parse_time(None) is None
    assert caveat._parse_time("") is None


def test_caveat_parse_date():
    assert caveat._parse_date("2026-04-18") == date(2026, 4, 18)
    assert caveat._parse_date(None) is None
    assert caveat._parse_date("") is None


ASYLUM_API_JSON = [
    {
        "id": "924c9a80-1f38-4b23-90e2-557af56746e9",
        "title": "Shitzprobe",
        "description": "<h4>A wild comedy show</h4><p>Hosted by <b>comics</b>.</p>",
        "start": "2026-04-20T23:00:00.000Z",
        "end": "2026-04-21T00:30:00.000Z",
        "imageUrl": "https://static.tixr.com/img1.jpg",
        "price": 30,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175311",
        "status": "available",
        "sales": [
            {"id": 1956494, "name": "General Admission", "currentPrice": 30, "state": "OPEN"},
        ],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
    {
        "id": "aaa11111-2222-3333-4444-555566667777",
        "title": "Shitzprobe",
        "description": "<h4>A wild comedy show</h4><p>Hosted by <b>comics</b>.</p>",
        "start": "2026-05-04T23:00:00.000Z",
        "end": "2026-05-05T00:30:00.000Z",
        "imageUrl": "https://static.tixr.com/img2.jpg",
        "price": 30,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175312",
        "status": "available",
        "sales": [],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
    {
        "id": "bbb22222-3333-4444-5555-666677778888",
        "title": "Chris Hall",
        "description": "<p>An evening of magic.</p>",
        "start": "2026-04-22T23:30:00.000Z",
        "end": "2026-04-23T01:00:00.000Z",
        "imageUrl": "https://static.tixr.com/img3.jpg",
        "price": 25,
        "venue": "Asylum NYC",
        "ticketUrl": "https://www.tixr.com/groups/asylumnyc/events/chris-hall-123",
        "status": "available",
        "sales": [],
        "timezone": "America/New_York",
        "matchedCategories": [],
    },
]


def test_asylum_strip_html():
    assert strip_html("<h4>Hello</h4><p>World</p>") == "Hello World"
    assert strip_html("") == ""
    assert strip_html("plain text") == "plain text"
    assert strip_html("<b>bold</b> and <i>italic</i>") == "bold and italic"


def test_asylum_format_price():
    assert format_price(30) == "$30"
    assert format_price(25.50) == "$25.50"
    assert format_price(0) == "Free"
    assert format_price(None) == ""
    assert format_price("invalid") == ""


def test_asylum_parse_api_events():
    bundle = parse_api_events(ASYLUM_API_JSON)

    # Should group by title: 2 Shitzprobe events -> 1 production, Chris Hall -> 1 production
    assert len(bundle.productions) == 2
    titles = {p.title for p in bundle.productions}
    assert titles == {"Shitzprobe", "Chris Hall"}

    # Should have 3 series total (one per event instance)
    assert len(bundle.series) == 3

    # Verify UTC -> ET conversion for first Shitzprobe event
    # 2026-04-20T23:00:00Z = 2026-04-20 19:00 ET (EDT, UTC-4)
    shitz_series = [s for s in bundle.series if s.title == "Shitzprobe"]
    assert len(shitz_series) == 2
    first = shitz_series[0]
    assert first.dates == [date(2026, 4, 20)]
    assert first.start_times == [time(19, 0)]
    assert first.end_time == time(20, 30)

    # Verify Chris Hall UTC -> ET conversion
    # 2026-04-22T23:30:00Z = 2026-04-22 19:30 ET (EDT, UTC-4)
    chris_series = [s for s in bundle.series if s.title == "Chris Hall"]
    assert len(chris_series) == 1
    assert chris_series[0].dates == [date(2026, 4, 22)]
    assert chris_series[0].start_times == [time(19, 30)]
    assert chris_series[0].end_time == time(21, 0)


def test_asylum_production_metadata():
    bundle = parse_api_events(ASYLUM_API_JSON)

    shitz_prod = [p for p in bundle.productions if p.title == "Shitzprobe"][0]
    assert shitz_prod.theater_id == "asylum"
    assert shitz_prod.theater_name == "Asylum NYC"
    assert shitz_prod.venue_name == "Asylum NYC"
    assert shitz_prod.venue_address == "123 E 24th St, New York, NY 10010"
    assert shitz_prod.price == "$30"
    assert shitz_prod.schedule_granularity == "instance"
    assert "wild comedy show" in shitz_prod.description
    assert "<" not in shitz_prod.description  # HTML tags stripped
    assert shitz_prod.ticket_url == "https://www.tixr.com/groups/asylumnyc/events/shitzprobe-175311"


def test_asylum_empty_api():
    bundle = parse_api_events([])
    assert len(bundle.productions) == 0
    assert len(bundle.series) == 0


def test_asylum_extract_events_list():
    # Plain list format
    events = [{"title": "A"}]
    assert extract_events_list(events) == [{"title": "A"}]

    # Dict with "events" key (actual API format)
    wrapped = {"events": [{"title": "B"}], "total": 1, "timezone": "America/New_York"}
    assert extract_events_list(wrapped) == [{"title": "B"}]

    # Unrecognized format
    assert extract_events_list("bad") is None
    assert extract_events_list({"no_events_key": True}) is None


# --- HERE Arts Center schedule parser tests ---

_REF_DATE = date(2026, 4, 18)


def test_here_parse_format_a_simple():
    """Format A: 'Day, M/D at H:MM pm'"""
    lines = ["Friday, 4/10 at 8:30 pm"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 4, 10), time(20, 30))]


def test_here_parse_format_a_with_annotation():
    """Parenthetical annotations like (PREVIEW) are stripped."""
    lines = ["Sunday, 4/5 at 4 pm (PREVIEW)"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 4, 5), time(16, 0))]


def test_here_parse_format_a_combined_times():
    """Two times on the same date: '4 pm & at 8:30 pm'"""
    lines = ["Saturday, 4/11 at 4 pm & at 8:30 pm"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [
        (date(2026, 4, 11), time(16, 0)),
        (date(2026, 4, 11), time(20, 30)),
    ]


def test_here_parse_format_a_missing_at():
    """Missing 'at' before the first time: 'Saturday, 4/18 4 pm & at 8:30 pm'"""
    lines = ["Saturday, 4/18 4 pm & at 8:30 pm (Post Show w/Community Service Society of NY)"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [
        (date(2026, 4, 18), time(16, 0)),
        (date(2026, 4, 18), time(20, 30)),
    ]


def test_here_parse_format_a_complex_annotation():
    """Multiple annotations: (MASK REQUIRED) (Post Show w/Legal Aid Society)"""
    lines = ["Sunday, 4/12 at 4 pm (MASK REQUIRED) (Post Show w/Legal Aid Society)"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 4, 12), time(16, 0))]


def test_here_parse_format_b_simple():
    """Format B: 'Day Month D @ H pm'"""
    lines = ["Saturday June 13 @ 7 pm (PREVIEW)"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 6, 13), time(19, 0))]


def test_here_parse_format_b_combined_times():
    """Format B with 'and @': 'Saturday June 20 @ 2 pm and @ 7 pm'"""
    lines = ["Saturday June 20 @ 2 pm and @ 7 pm"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [
        (date(2026, 6, 20), time(14, 0)),
        (date(2026, 6, 20), time(19, 0)),
    ]


def test_here_parse_format_b_extra_at():
    """Format B with extra 'at': 'Tuesday June 16 @ at 7 pm'"""
    lines = ["Tuesday June 16 @ at 7 pm (PREVIEW)"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 6, 16), time(19, 0))]


def test_here_parse_format_b_no_space_in_time():
    """Format B with no space in time: '2pm and @ 7pm'"""
    lines = ["Sunday June 21 @ 2pm and @ 7pm"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [
        (date(2026, 6, 21), time(14, 0)),
        (date(2026, 6, 21), time(19, 0)),
    ]


def test_here_parse_multiple_lines():
    """Multiple lines produce correct list of pairs."""
    lines = [
        "Sunday, 4/5 at 4 pm (PREVIEW)",
        "Tuesday, 4/7 at 8:30 pm (PREVIEW)",
        "Saturday, 4/11 at 4 pm & at 8:30 pm",
    ]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert len(result) == 4
    assert result[0] == (date(2026, 4, 5), time(16, 0))
    assert result[1] == (date(2026, 4, 7), time(20, 30))
    assert result[2] == (date(2026, 4, 11), time(16, 0))
    assert result[3] == (date(2026, 4, 11), time(20, 30))


def test_here_parse_empty_lines():
    """Empty input returns empty list."""
    assert parse_here_schedule_lines([]) == []


def test_here_parse_non_schedule_lines():
    """Lines without schedule data are ignored."""
    lines = [
        "Buy Tickets",
        "HERE Produces",
        "A wonderful show about justice.",
    ]
    assert parse_here_schedule_lines(lines, reference_date=_REF_DATE) == []


def test_here_parse_format_c_ordinal_day():
    """Format C: 'Thursday, April 30th, 8:30pm + Q&A'"""
    lines = ["Thursday, April 30th, 8:30pm + Q&A"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 4, 30), time(20, 30))]


def test_here_parse_format_c_ordinal_day_st():
    """Format C with 'st' ordinal: 'Friday, May 1st, 8:30pm'"""
    lines = ["Friday, May 1st, 8:30pm + Q&A"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 5, 1), time(20, 30))]


def test_here_parse_format_d_no_day_of_week():
    """Format D: 'May 13th at 6:30PM' (no day-of-week)"""
    lines = ["May 13th at 6:30PM"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 5, 13), time(18, 30))]


def test_here_parse_bare_time_no_ampm():
    """Times without am/pm: 'Wednesday, May 13 @ 8:30' defaults to PM."""
    lines = ["Wednesday, May 13 @ 8:30"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 5, 13), time(20, 30))]


def test_here_parse_bare_time_single_digit():
    """Bare single digit time: 'Saturday, May 16 @ 4' defaults to 4 PM."""
    lines = ["Saturday, May 16 @ 4"]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [(date(2026, 5, 16), time(16, 0))]


def test_here_parse_mixed_bare_and_ampm():
    """Bare time followed by am/pm time on the same date."""
    lines = [
        "Tuesday, June 9 @ 9PM",
        "Thursday, June 18 @ 8:30",
    ]
    result = parse_here_schedule_lines(lines, reference_date=_REF_DATE)
    assert result == [
        (date(2026, 6, 9), time(21, 0)),
        (date(2026, 6, 18), time(20, 30)),
    ]


def test_slipper_room_parse_wix_datetime():
    result = _parse_wix_datetime("Apr 18, 2026, 8:00 PM")
    assert result == (date(2026, 4, 18), time(20, 0))

    result = _parse_wix_datetime("May 3, 2026, 5:00 PM")
    assert result == (date(2026, 5, 3), time(17, 0))

    result = _parse_wix_datetime("Dec 31, 2026, 10:45 PM")
    assert result == (date(2026, 12, 31), time(22, 45))

    result = _parse_wix_datetime("no date here")
    assert result is None


def test_slipper_room_parse_wix_datetime_in_context():
    # Datetime embedded in longer text (as it appears in the detail card)
    text = "Some title Apr 18, 2026, 8:00 PM New York, 167 Orchard St"
    result = _parse_wix_datetime(text)
    assert result == (date(2026, 4, 18), time(20, 0))


def test_slipper_room_strip_date_suffix():
    # Period before month name
    assert _strip_date_suffix("Mr. Choade's Upstairs Downstairs. April 18") == "Mr. Choade's Upstairs Downstairs"
    assert _strip_date_suffix("Guest Event: Visceral Abstractions. April 20") == "Guest Event: Visceral Abstractions"
    assert _strip_date_suffix("Slippery Sundays. May 10") == "Slippery Sundays"
    # No period before month name (space only)
    assert _strip_date_suffix("The Slipper Room Show! May 1") == "The Slipper Room Show!"
    assert _strip_date_suffix("The Glitter Gutter!!! April 22") == "The Glitter Gutter!!!"
    assert _strip_date_suffix("Slipper Room Midnight Show. April 18") == "Slipper Room Midnight Show"
    # No date suffix at all
    assert _strip_date_suffix("A Simple Title") == "A Simple Title"
