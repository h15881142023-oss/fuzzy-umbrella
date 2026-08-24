#!/usr/bin/env bash
# LR 日报 / 日利润数据源：每天 23:30
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="top.chuanzangyiqu.lr-daily-local"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
WRAPPER="$ROOT/scripts/run_lr_daily_local.sh"
chmod +x "$WRAPPER"

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
    <integer>23</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/lr_daily_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/lr_daily_launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "已安装: $PLIST"
echo "每天 23:30 执行: $WRAPPER"
echo "卸载: bash $ROOT/scripts/uninstall_lr_daily_launchd.sh"
