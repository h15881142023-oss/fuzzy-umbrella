#!/usr/bin/env bash
# 列出本机 Chrome 所有资料（名称 ↔ Profile 目录）
set -euo pipefail
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/Library/Application Support/Google/Chrome/Local State")
if not os.path.exists(p):
    print("未找到 Chrome 配置")
    raise SystemExit(1)
data = json.load(open(p, encoding="utf-8"))
info = data.get("profile", {}).get("info_cache", {})
print("Profile目录\t显示名称\t账号")
for k, v in sorted(info.items()):
    print(f"{k}\t{v.get('name','')}\t{v.get('user_name','')}")
PY
echo ""
echo "川藏一区映射见: scrapers/city_chrome_profiles.json"
