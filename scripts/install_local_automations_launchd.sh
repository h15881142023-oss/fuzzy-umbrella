#!/usr/bin/env bash
# 安装全部本机自动化 launchd（替代 Cursor Cloud Automations）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/scripts/install_kpi_todo_launchd.sh"
bash "$ROOT/scripts/install_lr_daily_launchd.sh"
bash "$ROOT/scripts/install_visit_check_launchd.sh"
bash "$ROOT/scripts/install_store_morning_monitor_launchd.sh"

echo ""
echo "全部本机定时任务已安装。"
echo "请到 https://cursor.com/automations 停用这 5 个 Cloud 自动化，避免重复执行："
echo "  1. 川藏一区Todo周报"
echo "  2. LR日报日更（Cloud 23:30）"
echo "  3. 日利润数据源推送"
echo "  4. 拜访检核日更（Cloud）"
echo "  5. 自配门店早间监控（云端）"
echo ""
echo "说明见: scripts/LOCAL_AUTOMATIONS.md"
echo "卸载: bash $ROOT/scripts/uninstall_local_automations_launchd.sh"
