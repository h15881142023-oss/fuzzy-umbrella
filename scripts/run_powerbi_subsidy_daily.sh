#!/usr/bin/env bash
# 代补看板日更入口：确保 Power BI Chrome CDP 可用后执行抓取
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/bin:$PATH"
mkdir -p logs

# shellcheck disable=SC1091
source .venv/bin/activate

LOG="logs/powerbi_subsidy_daily.log"
echo "==== $(date '+%Y-%m-%d %H:%M:%S') start ====" >>"$LOG"

ensure_chrome() {
  if curl -s --max-time 2 "http://127.0.0.1:9222/json/version" >/dev/null 2>&1; then
    echo "CDP 9222 已就绪" | tee -a "$LOG"
    return 0
  fi
  if pgrep -x "Google Chrome" >/dev/null 2>&1; then
    echo "Chrome 在跑但无 CDP，请 Cmd+Q 退出后由本脚本拉起 Power BI Chrome" | tee -a "$LOG"
    return 1
  fi
  bash scripts/start_chrome_powerbi.sh | tee -a "$LOG"
}

# 从 9:00 起允许一直等到出数；若 CDP 起不来则每 10 分钟重试启动
while true; do
  if ensure_chrome; then
    break
  fi
  echo "10 分钟后重试启动 Chrome…" | tee -a "$LOG"
  sleep 600
done

# 传透参数（如 --once）
set +e
python scrapers/powerbi_subsidy_daily.py "$@" >>"$LOG" 2>&1
code=$?
set -e
echo "==== $(date '+%Y-%m-%d %H:%M:%S') exit=$code ====" >>"$LOG"
exit "$code"
