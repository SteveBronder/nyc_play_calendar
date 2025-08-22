from datetime import time
from nyc_events_etl.date_parsing import parse_dates, parse_times


def test_parse_multiple_dates():
    dates = parse_dates("Aug 3 & 6", 2025)
    assert len(dates) == 2
    assert dates[0].month == 8 and dates[0].day == 3
    assert dates[1].day == 6


def test_parse_date_range():
    dates = parse_dates("Aug 21-24", 2025)
    assert [d.day for d in dates] == [21, 22, 23, 24]


def test_parse_ordinal_weekday():
    dates = parse_dates("first Sunday of every month", 2025, default_month=8)
    assert dates[0].month == 8
    assert dates[0].day == 3


def test_parse_every_weekday():
    dates = parse_dates("every thursday", 2025, default_month=8)
    assert [d.day for d in dates] == [7, 14, 21, 28]


def test_parse_through_range():
    dates = parse_dates("through Aug 24", 2025)
    assert len(dates) == 24
    assert dates[-1].day == 24


def test_parse_time_range():
    starts, end = parse_times("4-9 pm")
    assert starts[0] == time(16, 0)
    assert end == time(21, 0)


def test_parse_multiple_times():
    starts, end = parse_times("7 & 9:30 pm")
    assert end is None
    assert starts == [time(19, 0), time(21, 30)]


def test_parse_with_doors():
    starts, end = parse_times("7 pm (6 pm doors)")
    assert starts[0] == time(19, 0)
    assert end is None
