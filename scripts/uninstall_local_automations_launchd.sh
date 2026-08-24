#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/uninstall_kpi_todo_launchd.sh"
bash "$ROOT/scripts/uninstall_lr_daily_launchd.sh"
bash "$ROOT/scripts/uninstall_visit_check_launchd.sh"
bash "$ROOT/scripts/uninstall_store_morning_monitor_launchd.sh"
echo "全部本机自动化 launchd 已卸载"
