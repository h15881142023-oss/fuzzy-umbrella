#!/usr/bin/env bash
# 用指定城市的 Chrome 资料启动浏览器（供 CDP 抓取）
# 用法: bash scripts/start_chrome_city.sh 仁寿县
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CITY="${1:-}"
if [[ -z "$CITY" ]]; then
  echo "用法: bash scripts/start_chrome_city.sh <城市名>"
  echo "城市: 仁寿县 南溪 叙永 彭州市 合江县（也可用简称：仁寿 彭州 合江）"
  exit 1
fi

# macOS bash 3.2 不支持在 eval "$(python <<'PY')" 内嵌 heredoc，改用临时文件 source
_env_file=$(mktemp "${TMPDIR:-/tmp}/chuanzang-chrome-env.XXXXXX")
trap 'rm -f "$_env_file"' EXIT
CONFIG_ROOT="$ROOT" CONFIG_CITY="$CITY" python3 - <<'PY' > "$_env_file"
import json, os, shlex
from pathlib import Path

ROOT = os.environ["CONFIG_ROOT"]
city = os.environ["CONFIG_CITY"]
cfg = json.loads((Path(ROOT) / "scrapers/city_chrome_profiles.json").read_text(encoding="utf-8"))
cities = cfg.get("cities", {})
resolved = None
if city in cities:
    resolved = city
else:
    for name, item in cities.items():
        aliases = item.get("aliases") or []
        if city in aliases:
            resolved = name
            break
if not resolved:
    raise SystemExit(f"未知城市: {city}")
item = cities[resolved]
user_data = os.path.expanduser(cfg.get("chrome_user_data_dir", "~/Library/Application Support/Google/Chrome"))
port = int(cfg.get("debug_port", 9222))
url = cfg.get("dashboard_url", "https://jx.ocrm.meituan.com/report/agentDashboard/unitDashboard.html")
prof = item["profile_directory"]
print(f"export USER_DATA_DIR={shlex.quote(user_data)}")
print(f"export PROFILE_DIR={shlex.quote(prof)}")
print(f"export DEBUG_PORT={port}")
print(f"export DASHBOARD_URL={shlex.quote(url)}")
print(f"export PROFILE_NAME={shlex.quote(item.get('profile_name', resolved))}")
print(f"export CITY_RESOLVED={shlex.quote(resolved)}")
PY
# shellcheck source=/dev/null
source "$_env_file"

CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME_APP" ]]; then
  echo "未找到 Google Chrome"
  exit 1
fi

if pgrep -x "Google Chrome" >/dev/null 2>&1; then
  echo "检测到 Chrome 正在运行。切换城市资料前请先完全退出 Chrome（Cmd+Q）。"
  echo "或在抓取时用 scripts/scrape_all_cities.sh 自动逐个切换。"
  exit 1
fi

# CDP 镜像目录；抓取前同步一次，确保登录态与日常 Chrome 一致
if [[ "${CHUANZANG_SKIP_SYNC:-}" != "1" ]]; then
  if [[ ! -f "$USER_DATA_DIR/Local State" ]]; then
    echo "首次使用，正在准备 CDP 镜像目录…"
    bash "$ROOT/scripts/setup_chrome_profiles.sh"
  else
    bash "$ROOT/scripts/sync_chrome_to_cdp.sh"
  fi
fi

if curl -s --max-time 1 "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
  echo "调试端口 ${DEBUG_PORT} 已被占用"
  exit 1
fi

echo "启动 Chrome：城市=${CITY}  资料=${PROFILE_NAME} (${PROFILE_DIR})  端口=${DEBUG_PORT}"
nohup "$CHROME_APP" \
  --remote-debugging-port="${DEBUG_PORT}" \
  --remote-allow-origins=* \
  --user-data-dir="${USER_DATA_DIR}" \
  --profile-directory="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  "${DASHBOARD_URL}" \
  > "/tmp/chuanzang-chrome-${CITY}.log" 2>&1 &

# Chrome 冷启动较慢，最多等 30 秒检测调试端口
_ready=0
for _i in $(seq 1 30); do
  if curl -s --max-time 2 "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
    _ready=1
    break
  fi
  sleep 1
done

if [[ "$_ready" -eq 1 ]]; then
  echo "OK: 已打开 ${CITY} 的看板。请确认页面数据正常后："
  echo "  export MEITUAN_ACTIVE_CITY='${CITY}'"
  echo "  bash scripts/scrape_meituan_all.sh"
else
  echo "调试端口 ${DEBUG_PORT} 未就绪（页面可能已打开，但 CDP 未启用）。"
  echo "请先运行: bash scripts/setup_chrome_profiles.sh"
  echo "日志: /tmp/chuanzang-chrome-${CITY}.log"
  exit 1
fi
