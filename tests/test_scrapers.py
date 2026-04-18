from datetime import date, time

from nyc_events_etl.scrapers import frigid, public_theater
from nyc_events_etl.scrapers.here import parse_here_schedule_lines

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
