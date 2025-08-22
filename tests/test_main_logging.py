import logging
from logging.handlers import RotatingFileHandler
from datetime import date, time

import pytest

from nyc_events_etl.models import EventSeries
from nyc_events_etl import __main__ as main


def make_series():
    return EventSeries(
        title="T",
        description="D",
        price="$0",
        venue_name="V",
        venue_address="A",
        dates=[date(2025, 8, 1)],
        start_times=[time(19, 0)],
    )


def test_configure_logging_and_hook(monkeypatch, tmp_path):
    monkeypatch.setenv("NYC_EVENTS_LOG_LEVEL", "DEBUG")
    log_path = tmp_path / "app.log"
    logger, watcher = main.configure_logging(log_file=str(log_path))
    assert logger.level == logging.DEBUG
    assert any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    logger.error("boom")
    with pytest.raises(SystemExit):
        main.raise_on_error(watcher)


def test_run_etl_logs_counts_and_totals(monkeypatch, caplog):
    series = make_series()
    monkeypatch.setattr(main.pdf_parser, "parse_pdf", lambda *a, **k: [series])
    monkeypatch.setattr(main.frigid, "parse_html", lambda *a, **k: [series])
    monkeypatch.setattr(main.public_theater, "parse_html", lambda *a, **k: [series])

    class GC:
        def __init__(self):
            self.calls = []

        def upsert_event(self, event):
            self.calls.append(event)
            return "inserted"

    gc = GC()

    caplog.set_level(logging.INFO, logger="nyc_events_etl")
    main.run_etl(dry_run=False, gc_client=gc)
    text = "\n".join(caplog.messages)
    assert "PDF: 1 series parsed, 1 instances expanded" in text
    assert "Frigid: 1 series parsed, 1 instances expanded" in text
    assert "Public Theater: 1 series parsed, 1 instances expanded" in text
    assert "Google Calendar: 3 inserted, 0 updated, 0 deleted" in text

