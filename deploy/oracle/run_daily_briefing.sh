#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/briefstock}"
cd "$PROJECT_DIR"

source .venv/bin/activate
python -m daily_stock_briefing.jobs.run_daily_briefing --date "$(TZ=Asia/Seoul date +%F)"
