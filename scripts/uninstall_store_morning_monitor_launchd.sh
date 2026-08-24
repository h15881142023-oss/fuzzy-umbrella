#!/usr/bin/env bash
LABEL="top.chuanzangyiqu.store-morning-local"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
rm -f "$PLIST"
echo "已卸载自配门店早间监控 launchd"
