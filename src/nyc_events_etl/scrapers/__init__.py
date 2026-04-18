"""HTML scraper modules for various event sources."""

from . import astor_place, asylum, caveat, frigid, here, liberty, nytw, performance_space, public_theater, theater_for_the_new_city, vineyard, wild_project
from .registry import SCRAPER_REGISTRY

__all__ = [
    "SCRAPER_REGISTRY",
    "astor_place",
    "asylum",
    "caveat",
    "frigid",
    "here",
    "liberty",
    "nytw",
    "performance_space",
    "public_theater",
    "theater_for_the_new_city",
    "vineyard",
    "wild_project",
]
