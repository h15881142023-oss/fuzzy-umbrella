#!/usr/bin/env bash
# 一键抓取美团看板相关数据（需先 start_chrome_meituan.sh 并登录）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

python scrapers/scrape_dashboard_cdp.py
python scrapers/sync_catering_scores.py
python scrapers/sync_non_catering_scores.py
python scrapers/scrape_todo_achievement_cdp.py
python scrapers/scrape_meituan_cdp.py
echo "美团看板抓取完成"
