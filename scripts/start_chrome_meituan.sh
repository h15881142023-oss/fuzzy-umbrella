#!/usr/bin/env bash
# 以远程调试模式启动 Chrome（保留美团登录态）
set -euo pipefail

PORT="${MEITUAN_CDP_PORT:-9222}"
PROFILE="${MEITUAN_CHROME_PROFILE:-$HOME/.chuanzang_chrome_meituan}"
mkdir -p "$PROFILE"

if curl -s --max-time 1 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "Chrome 调试端口 ${PORT} 已在运行"
  exit 0
fi

CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME_APP" ]]; then
  echo "未找到 Google Chrome，请安装后重试"
  exit 1
fi

echo "启动 Chrome（端口 ${PORT}，配置目录 ${PROFILE}）"
nohup "$CHROME_APP" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE}" \
  --no-first-run \
  --no-default-browser-check \
  "https://jx.ocrm.meituan.com/report/agentDashboard/unitDashboard.html" \
  > /tmp/chuanzang-chrome-meituan.log 2>&1 &

sleep 2
if curl -s --max-time 3 "http://127.0.0.1:${PORT}/json/version" >/dev/null; then
  echo "OK: 请在打开的 Chrome 中登录美团后台，然后保持窗口不关"
else
  echo "启动可能失败，查看日志: /tmp/chuanzang-chrome-meituan.log"
  exit 1
fi
