import sys
from types import SimpleNamespace
from nyc_events_etl.pdf_parser import parse_pdf


def test_parse_pdf(monkeypatch, tmp_path):
    sample = (
        "Marc's Unique Antiques Estate Sale – Vintage goods; 8:30 am-4 pm; Aug 3 & 6 – Free – Marc's Antiques – 123 Main St"
    )

    class DummyCM:
        def __enter__(self):
            page = SimpleNamespace(extract_text=lambda: sample)
            return SimpleNamespace(pages=[page])

        def __exit__(self, *args):
            return False

    fake_pdfplumber = SimpleNamespace(open=lambda path: DummyCM())
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)
    events = parse_pdf(tmp_path / "dummy.pdf", 2025, 8)
    assert len(events) == 1
    series = events[0]
    assert series.title.startswith("Marc's Unique")
    assert series.dates[0].day == 3 and series.dates[1].day == 6
