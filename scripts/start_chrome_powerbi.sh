#!/usr/bin/env bash
# 用 Default 资料启动 Power BI（开启 CDP 9222）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POWERBI_URL="${1:-https://app.powerbi.com/reportEmbed?reportId=002a894f-ba61-4a4c-b99c-b275e5e4142f&autoAuth=true&ctid=7c792a97-2300-4444-aa97-172fed9b0501}"
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="$HOME/Library/Application Support/Google/ChromeAutomation"
DEBUG_PORT=9222

if [[ ! -x "$CHROME_APP" ]]; then
  echo "未找到 Google Chrome"
  exit 1
fi

if pgrep -x "Google Chrome" >/dev/null 2>&1; then
  echo "请先完全退出 Chrome（Cmd+Q）后重试。"
  exit 1
fi

bash "$ROOT/scripts/sync_chrome_to_cdp.sh"

if curl -s --max-time 1 "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
  echo "调试端口 ${DEBUG_PORT} 已被占用"
  exit 1
fi

echo "启动 Power BI（Profile=Default, 端口=${DEBUG_PORT}）"
nohup "$CHROME_APP" \
  --remote-debugging-port="${DEBUG_PORT}" \
  --remote-allow-origins=* \
  --user-data-dir="${USER_DATA_DIR}" \
  --profile-directory="Default" \
  --no-first-run \
  --no-default-browser-check \
  "${POWERBI_URL}" \
  > /tmp/chuanzang-chrome-powerbi.log 2>&1 &

for _i in $(seq 1 30); do
  if curl -s --max-time 2 "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
    echo "OK: Power BI 已打开，可运行:"
    echo "  python scrapers/scrape_delivery_fee_daily_cdp.py"
    exit 0
  fi
  sleep 1
done

echo "启动失败，查看日志: /tmp/chuanzang-chrome-powerbi.log"
exit 1
