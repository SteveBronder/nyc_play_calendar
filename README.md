# nyc_play_calendar

## Cron job

The repository includes a helper script at `scripts/cron_example.sh` that prepares the
environment and invokes the `nyc-events` CLI.

1. Install dependencies with Poetry so that `.venv` contains the project.
2. Store Google API credentials at `.secrets/service_account.json` (this file is not
   tracked by git). The script exports `GOOGLE_APPLICATION_CREDENTIALS` pointing to it.
3. Logs are written to `logs/nyc-events.log`. The script will create the `logs`
   directory if needed.

### Installing the cron job

Edit your crontab and add an entry that points to the script. For example, to run the
ETL every night at 2 AM:

```
0 2 * * * /path/to/nyc_play_calendar/scripts/cron_example.sh
```

Adjust the schedule and paths as necessary for your system.
