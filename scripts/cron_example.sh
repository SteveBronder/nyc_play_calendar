#!/usr/bin/env bash
set -euo pipefail

# Example cron script for running nyc-events nightly.
# Adjust paths as needed for your environment.

# Resolve repository root (directory containing this script is scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure virtualenv binaries are available
export PATH="$REPO_ROOT/.venv/bin:$PATH"

# Location of Google API credentials (not committed to git)
export GOOGLE_APPLICATION_CREDENTIALS="$REPO_ROOT/.secrets/service_account.json"

# Log directory
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

# Run the ETL
nyc-events >> "$LOG_DIR/nyc-events.log" 2>&1
