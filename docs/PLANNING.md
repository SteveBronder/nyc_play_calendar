# NYC Events ETL - Planning

This document outlines the high level plan for building the NYC Events ETL
pipeline. It summarizes the major components and immediate next steps.

## Components

* **PDF parser** - extract structured event listings from the monthly curated PDF
  documents. Handles fuzzy dates, times, ranges and recurring rules.
* **Website scrapers** - site specific scrapers for event calendars. Start with
  simple HTTP/HTML parsing and fall back to a headless browser when content is
  rendered dynamically.
* **Normalization & models** - convert parsed data into a unified
  representation. Expand recurring rules into individual event instances.
* **Exporters** - emit events to an ICS file and upsert them into Google
  Calendar using stable UIDs to avoid duplicates.
* **Logging & CLI** - provide a command line entry point, structured logging and
  options for dry runs or verbose output.

## Near term tasks

1. Set up project scaffolding with stub modules for the parser, scraper,
   normalization models, exporters and pipeline orchestration.
2. Flesh out the command line interface so it calls the pipeline entry point.
3. Implement basic dataclasses for event series and event instances.
4. Add minimal tests validating the CLI and models to ensure the foundation is
   in place.
5. Incrementally implement real parsing and scraping logic in future
   iterations.

