#!/usr/bin/env bash
# 本机：拜访检核日更（每天 09:00）端到端：导出 → 入库
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs data/visit_exports

LOG="logs/visit_check_local.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium >/dev/null 2>&1 || true

set +e
python scrapers/visit_check_scrape_live.py >>"$LOG" 2>&1
scrape_code=$?
if [[ $scrape_code -ne 0 ]]; then
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$scrape_code (export fail) ====" >>"$LOG"
  exit "$scrape_code"
fi

# 本机优先直写本地库；若设置 CZ_VISIT_PUSH_API=1 则走线上 API
if [[ "${CZ_VISIT_PUSH_API:-0}" == "1" ]]; then
  python scrapers/visit_check_daily.py --push-api "$@" >>"$LOG" 2>&1
else
  python scrapers/visit_check_daily.py "$@" >>"$LOG" 2>&1
fi
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
