#!/usr/bin/env bash
# 拜访检核日更：消费 Cloud 工作区导出，推送到平台 API（不落用户本机 Downloads）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
mkdir -p logs data/visit_exports

LOG="logs/visit_check_daily.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"
set +e
python scrapers/visit_check_daily.py --push-api "$@" >>"$LOG" 2>&1
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
