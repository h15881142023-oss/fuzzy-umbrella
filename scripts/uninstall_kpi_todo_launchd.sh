#!/usr/bin/env bash
LABEL="top.chuanzangyiqu.kpi-todo-local"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
rm -f "$PLIST"
echo "已卸载 KPI Todo launchd"
