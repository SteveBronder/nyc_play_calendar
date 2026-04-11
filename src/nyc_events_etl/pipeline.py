from __future__ import annotations

"""Playwright scrape/build orchestration."""

from dataclasses import replace
from pathlib import Path
from typing import Iterable
import logging
import re

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


def _normalize_title(title: str) -> str:
    """Normalize title for deduplication: lowercase, remove punctuation."""
    return re.sub(r"[^\w\s]", "", title).lower()


def deduplicate_productions(bundle: ScrapeBundle) -> ScrapeBundle:
    """Deduplicate productions with the same (theater_id, normalized_title).

    Keeps the production with the most series instances.
    This prevents duplicate shows when multiple scrapers cover the same show
    (e.g., wild_project scraper and frigid scraper both finding wild_project shows).
    """
    logger = logging.getLogger("nyc_events_etl")

    # Group productions by (theater_id, normalized_title)
    groups = {}
    for prod in bundle.productions:
        key = (prod.theater_id, _normalize_title(prod.title))
        if key not in groups:
            groups[key] = []
        groups[key].append(prod)

    # For each group, keep the one with the most instances
    kept_prod_ids = set()
    for (theater_id, norm_title), prods in groups.items():
        if len(prods) == 1:
            kept_prod_ids.add(prods[0].production_id)
            continue

        # Count instances for each production
        instance_counts = {}
        for prod in prods:
            count = sum(1 for s in bundle.series if s.production_id == prod.production_id)
            instance_counts[prod.production_id] = count

        # Keep the one with most instances
        best_prod_id = max(instance_counts, key=instance_counts.get)
        kept_prod_ids.add(best_prod_id)

        removed = [p.production_id for p in prods if p.production_id != best_prod_id]
        if removed:
            logger.info(
                "Deduplicate: keeping %s (%d instances) over %s for '%s' at %s",
                best_prod_id, instance_counts[best_prod_id],
                removed, prods[0].title, theater_id
            )

    # Filter productions and series to kept IDs
    filtered_prods = [p for p in bundle.productions if p.production_id in kept_prod_ids]
    filtered_series = [s for s in bundle.series if s.production_id in kept_prod_ids]

    if len(filtered_prods) < len(bundle.productions):
        logger.info(
            "Deduplication: %d → %d productions, %d → %d series",
            len(bundle.productions), len(filtered_prods),
            len(bundle.series), len(filtered_series)
        )

    return ScrapeBundle(
        productions=filtered_prods,
        series=filtered_series,
        warnings=bundle.warnings,
    )


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
    bundle = deduplicate_productions(bundle)
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
