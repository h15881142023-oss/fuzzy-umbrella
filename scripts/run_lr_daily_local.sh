#!/usr/bin/env bash
# 本机：LR 日报 + 日利润数据源推送（每天 23:30）端到端
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs data/lr_scrape lr/work lr/output

LOG="logs/lr_daily_local.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium >/dev/null 2>&1 || true

set +e
python lr/scrape_live.py >>"$LOG" 2>&1
scrape_code=$?
if [[ $scrape_code -ne 0 ]]; then
  echo "scrape failed" >>"$LOG"
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$scrape_code (scrape fail) ====" >>"$LOG"
  exit "$scrape_code"
fi
python lr/run_daily.py --scrape-json data/lr_scrape/latest.json >>"$LOG" 2>&1
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
