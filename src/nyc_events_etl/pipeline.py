from __future__ import annotations

"""Playwright scrape/build orchestration."""

from dataclasses import replace
from pathlib import Path
from typing import Iterable
import logging

from playwright.sync_api import sync_playwright

from .build import load_artifact, render_site, write_artifact
from .models import ScrapeBundle
from .normalization import expand_series
from .scrapers.common import merge_bundles
from .scrapers.registry import SCRAPER_REGISTRY

DEFAULT_ARTIFACT_PATH = Path("data/events.json")
DEFAULT_SITE_DIR = Path("docs")
POETRY_OUTPUT_ROOT = Path("data")
POETRY_SITE_DIR = POETRY_OUTPUT_ROOT / "docs"


def scrape_theaters(theater_ids: Iterable[str] | None = None) -> ScrapeBundle:
    logger = logging.getLogger("nyc_events_etl")
    selected_ids = list(theater_ids or SCRAPER_REGISTRY.keys())
    logger.info("Starting scrape for theaters: %s", ", ".join(selected_ids))
    bundles = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        for theater_id in selected_ids:
            scraper = SCRAPER_REGISTRY[theater_id]
            logger.info("Scraping %s", theater_id)
            try:
                bundle = scraper.scrape(context)
            except Exception as exc:
                logger.exception("Scraper failed for %s", theater_id)
                bundle = ScrapeBundle(warnings=[f"{theater_id}: {exc}"])
            logger.info(
                "Finished %s: %d productions, %d series, %d warnings",
                theater_id,
                len(bundle.productions),
                len(bundle.series),
                len(bundle.warnings),
            )
            bundles.append(bundle)
        context.close()
        browser.close()
    return merge_bundles(bundles)


def materialize_instances(bundle: ScrapeBundle):
    instances = []
    for series in bundle.series:
        for event in expand_series(series):
            event.theater_id = series.theater_id
            event.theater_name = series.theater_name
            event.production_id = series.production_id
            event.source = series.source
            event.ticket_url = series.ticket_url
            instances.append(event)
    return instances


def run_scrape_artifact(
    *,
    theater_ids: Iterable[str] | None = None,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
) -> dict:
    logger = logging.getLogger("nyc_events_etl")
    bundle = scrape_theaters(theater_ids=theater_ids)
    instances = materialize_instances(bundle)
    logger.info(
        "Writing artifact with %d productions and %d instances to %s",
        len(bundle.productions),
        len(instances),
        artifact_path,
    )
    return write_artifact(bundle.productions, instances, artifact_path)


def run_site_build(
    *,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    site_dir: Path = DEFAULT_SITE_DIR,
) -> dict:
    payload = load_artifact(artifact_path)
    render_site(payload, site_dir)
    return payload


def run_full_build(
    *,
    theater_ids: Iterable[str] | None = None,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    site_dir: Path = DEFAULT_SITE_DIR,
) -> dict:
    payload = run_scrape_artifact(theater_ids=theater_ids, artifact_path=artifact_path)
    render_site(payload, site_dir)
    return payload


def poetry_output_build() -> None:
    """Poetry entrypoint that writes all generated output under ``data/``."""

    run_full_build(
        artifact_path=POETRY_OUTPUT_ROOT / "events.json",
        site_dir=POETRY_SITE_DIR,
    )
