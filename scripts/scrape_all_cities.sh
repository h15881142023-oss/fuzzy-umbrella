#!/usr/bin/env bash
# 依次用五个城市的 Chrome 资料抓取看板（自动开关 Chrome）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

CITIES=(仁寿县 南溪 叙永 彭州市 合江县)
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

quit_chrome() {
  if pgrep -x "Google Chrome" >/dev/null 2>&1; then
    echo "关闭 Chrome…"
    osascript -e 'tell application "Google Chrome" to quit' 2>/dev/null || true
    sleep 2
    pkill -x "Google Chrome" 2>/dev/null || true
    sleep 1
  fi
}

quit_chrome
echo "同步五城 Chrome 资料到 CDP 镜像（保留登录 Cookie）…"
bash scripts/sync_chrome_to_cdp.sh

for CITY in "${CITIES[@]}"; do
  echo "========== ${CITY} =========="
  quit_chrome
  if ! CHUANZANG_SKIP_SYNC=1 bash scripts/start_chrome_city.sh "$CITY"; then
    echo "跳过 ${CITY}"
    continue
  fi
  sleep 5
  export MEITUAN_ACTIVE_CITY="$CITY"
  python scrapers/scrape_dashboard_cdp.py || true
  python scrapers/sync_catering_scores.py || true
  python scrapers/sync_non_catering_scores.py || true
  quit_chrome
done

export MEITUAN_ACTIVE_CITY=""
echo "五城抓取流程结束。可在网站刷新查看。"
