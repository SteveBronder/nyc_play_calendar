# NYC Events ETL

Prototype ETL pipeline that will parse curated PDF event listings and selected
web calendars to produce normalized events. The final output will be an ICS file
and optional Google Calendar updates.

At the moment the project only contains scaffolding code:

* `cli.py` – command line entry point invoking the pipeline.
* `pdf_parser.py` – placeholder PDF parser.
* `models.py` – dataclasses for event series and instances.
* `exporters/ics.py` – write events to an ICS file.
* `pipeline.py` – simple orchestration tying the pieces together.

See `docs/PLANNING.md` for the high level roadmap.

## Development

```bash
poetry install
poetry run pytest
```

