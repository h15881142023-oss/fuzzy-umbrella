#!/usr/bin/env bash
# 安装 launchd：每个工作日/每天 09:00 自动跑代补抓取（一直等到出数）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="top.chuanzangyiqu.powerbi-subsidy-daily"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
WRAPPER="$ROOT/scripts/run_powerbi_subsidy_daily.sh"
chmod +x "$WRAPPER" "$ROOT/scripts/start_chrome_powerbi.sh"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${WRAPPER}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/powerbi_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/powerbi_launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "已安装: $PLIST"
echo "每天 09:00 自动执行: $WRAPPER"
echo "日志: $ROOT/logs/powerbi_subsidy_daily.log"
echo "手动试跑: bash $WRAPPER --once"
echo "卸载: bash $ROOT/scripts/uninstall_powerbi_daily_launchd.sh"
