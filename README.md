# nyc_play_calendar

Static site and scraper pipeline for NYC theater listings.

## Setup

Install dependencies with Poetry:

```bash
poetry install
```

Several scrapers use Playwright, so install the browser runtime once after the
Python dependencies are in place:

```bash
poetry run playwright install chromium
```

## Scrape and Regenerate the Site

The main workflow is:

1. Scrape the theater sites into a JSON artifact.
2. Render the static site from that artifact.

To do both in one command:

```bash
poetry run nyc-events build
```

By default this writes:

- `data/events.json`: the scraped artifact
- `docs/`: the regenerated static site

If you want a clean split between scraping and rendering, use the subcommands
directly.

Scrape only:

```bash
poetry run nyc-events scrape
```

Build the site from the existing artifact without re-scraping:

```bash
poetry run nyc-events build-site
```

You can also override the output locations:

```bash
poetry run nyc-events build \
  --artifact-path data/events.json \
  --site-dir docs
```

## Regenerate Only Specific Theaters

To limit a scrape to one or more theater ids, pass `--theater` multiple times:

```bash
poetry run nyc-events scrape --theater nytw --theater vineyard
poetry run nyc-events build --theater astor_place
```

Supported theater ids currently registered in the scraper pipeline:

- `astor_place`
- `frigid`
- `liberty`
- `nytw`
- `performance_space`
- `tnc`
- `vineyard`
- `wild_project`

## Poetry Data Build Shortcut

There is also a Poetry script that writes all generated output under `data/`:

```bash
poetry run nyc-events-data
```

That command writes:

- `data/events.json`
- `data/docs/`

Use this when you want to preserve the generated site under `data/` instead of
publishing it into the repo's `docs/` directory.

## Logging

The command line entry point configures logging with a rotating file handler
(`nyc_events.log`) and emits logs to the console. The log level defaults to
`INFO` but can be overridden with the environment variable
`NYC_EVENTS_LOG_LEVEL` (for example `DEBUG` or `WARNING`).

If any step in the pipeline logs an error the process exits with status code 1,
which allows cron or other schedulers to detect failures.

## Cron Job

The repository includes a helper script at `scripts/cron_example.sh` that
prepares the environment and invokes the `nyc-events` CLI.

To install it from cron, edit your crontab and add an entry that points to the
script. For example, to rebuild the site every night at 2 AM:

```bash
0 2 * * * /path/to/nyc_play_calendar/scripts/cron_example.sh
```

Adjust the schedule and paths as necessary for your system.

## Theater Sources

The current scraper coverage is based on these source sites:

- https://www.nytw.org/2025-26-season/
- https://vineyardtheatre.org/showsevents/
- https://www.libertytheatresusa.com/nowplaying/
- https://astorplacetheatre.com/productions/
- https://thewildproject.org/performances/
- https://performancespacenewyork.org/
- https://theaterforthenewcity.net/
