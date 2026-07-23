#!/usr/bin/env bash
# 本机：自配门店早间监控（每天 08:30）
# 默认复用代补/配送费早间抓取；可用环境变量覆盖命令。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

LOG="logs/store_morning_monitor_local.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"

CMD="${CZ_STORE_MORNING_CMD:-bash scripts/run_powerbi_subsidy_daily.sh --once}"

set +e
bash -lc "$CMD" >>"$LOG" 2>&1
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
