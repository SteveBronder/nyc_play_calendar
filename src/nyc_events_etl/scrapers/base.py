"""Base classes for web scrapers."""

from __future__ import annotations

from typing import Iterable

from ..models import EventSeries


class BaseScraper:
    """Interface for all site specific scrapers."""

    name: str = "base"

    def fetch(self) -> Iterable[EventSeries]:
        """Retrieve events from the target site.

        Returns an iterable of EventSeries objects. Subclasses must implement
        this method.
        """

        raise NotImplementedError

