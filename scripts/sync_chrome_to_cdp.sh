#!/usr/bin/env bash
# 把五城 Chrome 资料从日常目录同步到 CDP 镜像目录（真实文件夹，非符号链接）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

CHROME_SRC="${CHROME_SRC:-$HOME/Library/Application Support/Google/Chrome}"
CHROME_CDP="${CHROME_CDP:-$HOME/Library/Application Support/Google/ChromeAutomation}"

if [[ ! -d "$CHROME_SRC" ]]; then
  echo "未找到 Chrome 资料目录: $CHROME_SRC"
  exit 1
fi

if pgrep -x "Google Chrome" >/dev/null 2>&1; then
  echo "请先完全退出 Chrome（Cmd+Q），再同步资料。"
  exit 1
fi

# 旧方案若是符号链接，Chrome 仍会判定为默认目录导致 CDP 失效
if [[ -L "$CHROME_CDP" ]]; then
  echo "移除旧版符号链接（该方式无法开启 CDP）…"
  rm -f "$CHROME_CDP"
fi

mkdir -p "$CHROME_CDP"

if [[ -f "$CHROME_SRC/Local State" ]]; then
  cp -f "$CHROME_SRC/Local State" "$CHROME_CDP/Local State"
fi

synced=0
while IFS= read -r prof; do
  [[ -z "$prof" ]] && continue
  src="$CHROME_SRC/$prof"
  dst="$CHROME_CDP/$prof"
  if [[ ! -d "$src" ]]; then
    echo "警告: 源目录不存在 ${prof}"
    continue
  fi
  mkdir -p "$dst"
  rsync -a --delete "${src}/" "${dst}/"
  synced=$((synced + 1))
  echo "已同步: ${prof}"
done < <(CONFIG_ROOT="$ROOT" python3 - <<'PY'
import json, os
from pathlib import Path
root = os.environ["CONFIG_ROOT"]
cfg = json.loads((Path(root) / "scrapers/city_chrome_profiles.json").read_text(encoding="utf-8"))
seen = {"Default"}
print("Default")
for item in cfg.get("cities", {}).values():
    p = item["profile_directory"]
    if p not in seen:
        seen.add(p)
        print(p)
PY
)

rm -f "$CHROME_CDP/SingletonLock" "$CHROME_CDP/SingletonSocket" "$CHROME_CDP/SingletonCookie" 2>/dev/null || true

if [[ "$synced" -eq 0 ]]; then
  echo "没有同步任何资料"
  exit 1
fi

echo "OK: CDP 镜像已更新 -> ${CHROME_CDP} (${synced} 个资料)"
