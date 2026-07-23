#!/usr/bin/env bash
# KPI/Todo 周报：周一、周四 14:00
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="top.chuanzangyiqu.kpi-todo-local"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
WRAPPER="$ROOT/scripts/run_kpi_todo_local.sh"
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
  <array>
    <dict>
      <key>Weekday</key><integer>1</integer>
      <key>Hour</key><integer>14</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
    <dict>
      <key>Weekday</key><integer>4</integer>
      <key>Hour</key><integer>14</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
  </array>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/kpi_todo_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/kpi_todo_launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "已安装: $PLIST"
echo "周一/周四 14:00 执行: $WRAPPER"
echo "卸载: bash $ROOT/scripts/uninstall_kpi_todo_launchd.sh"
