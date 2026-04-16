#!/usr/bin/env bash
#
# Scrape theater listings, rebuild the static site, and push to GitHub.
# Intended for cron — logs to update_site.log in the project root.
#
set -euo pipefail

PROJECT_DIR="/home/steve/open_source/nyc_play_calendar"
LOG_FILE="${PROJECT_DIR}/update_site.log"
VENV="${PROJECT_DIR}/.venv/bin/activate"

exec >> "${LOG_FILE}" 2>&1
echo "--- $(date '+%Y-%m-%d %H:%M:%S') start ---"

cd "${PROJECT_DIR}"
source "${VENV}"

# 1. Scrape + build site in one step
python -m nyc_events_etl build

# 2. Commit any changes in docs/ (the built site served via GitHub Pages).
#    data/events.json is gitignored — it's an intermediate build artifact.
if git diff --quiet docs/; then
    echo "No changes to commit."
else
    git add docs/
    git commit -m "update site $(date '+%Y-%m-%d %H:%M')"
    git push origin main
    echo "Pushed updated site."
fi

echo "--- $(date '+%Y-%m-%d %H:%M:%S') done ---"
