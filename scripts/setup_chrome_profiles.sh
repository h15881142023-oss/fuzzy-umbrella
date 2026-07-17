#!/usr/bin/env bash
# 一次性准备 CDP 镜像目录（真实文件夹，可开启远程调试且保留登录态）
set -euo pipefail
bash "$(cd "$(dirname "$0")" && pwd)/sync_chrome_to_cdp.sh"
echo ""
echo "说明: 镜像目录与日常 Chrome 分离，但抓取前会自动同步最新登录态。"
echo "现在可运行: bash scripts/start_chrome_city.sh 仁寿县"
echo "或: bash scripts/scrape_all_cities.sh"
