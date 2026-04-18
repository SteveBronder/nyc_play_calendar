from __future__ import annotations

"""Registry of Playwright theater scrapers."""

from . import astor_place, asylum, frigid, liberty, nytw, performance_space, theater_for_the_new_city, vineyard, wild_project

SCRAPER_REGISTRY = {
    nytw.THEATER_ID: nytw,
    vineyard.THEATER_ID: vineyard,
    liberty.THEATER_ID: liberty,
    astor_place.THEATER_ID: astor_place,
    wild_project.THEATER_ID: wild_project,
    performance_space.THEATER_ID: performance_space,
    theater_for_the_new_city.THEATER_ID: theater_for_the_new_city,
    frigid.THEATER_ID: frigid,
    asylum.THEATER_ID: asylum,
}

