"""Pipeline orchestration for the NYC Events ETL."""

from __future__ import annotations

from typing import Iterable, List

from .models import EventInstance, EventSeries, expand_series
from .pdf_parser import parse_pdf
from .exporters import export_ics


class Pipeline:
    """Coordinates parsing, scraping, normalization and exporting."""

    def __init__(self) -> None:
        self.series: List[EventSeries] = []

    def run(self, pdf_path: str, ics_path: str) -> None:
        """Execute the pipeline for a given PDF and output ICS file.

        This minimal implementation only parses the PDF and writes the resulting
        events to an ICS file.
        """

        self.series.extend(parse_pdf(pdf_path))
        instances = [inst for s in self.series for inst in expand_series(s)]
        export_ics(instances, ics_path)

