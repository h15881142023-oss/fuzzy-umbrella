#!/usr/bin/env bash
# 本机：KPI/Todo 周报（周一/周四 14:00）端到端
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs data/kpi_todo_scrape kpi_todo/output

LOG="logs/kpi_todo_local.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium >/dev/null 2>&1 || true

set +e
python kpi_todo/scrape_live.py >>"$LOG" 2>&1
scrape_code=$?
if [[ $scrape_code -ne 0 ]]; then
  python kpi_todo/run_biweekly.py --notify-only --message "本机抓取失败，详见 logs/kpi_todo_local.log" >>"$LOG" 2>&1
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$scrape_code (scrape fail) ====" >>"$LOG"
  exit "$scrape_code"
fi
python kpi_todo/run_biweekly.py --scrape-json data/kpi_todo_scrape/latest.json >>"$LOG" 2>&1
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
