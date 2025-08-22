# nyc_play_calendar

## Logging

The command line entry point configures logging with a rotating file handler
(`nyc_events.log`) and emits logs to the console. The log level defaults to
`INFO` but can be overridden with the environment variable
`NYC_EVENTS_LOG_LEVEL` (e.g. `DEBUG`, `WARNING`).

If any step in the pipeline logs an error the process exits with status code 1,
which allows cron or other schedulers to detect failures.
