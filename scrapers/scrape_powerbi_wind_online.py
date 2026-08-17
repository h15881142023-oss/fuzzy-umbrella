"""抓取 Power BI「业务数据风向看板」川藏一区五城在线商家数。

依赖本机已登录的 Chrome CDP 9222：
  Windows: powershell -File .\\scripts\\start_chrome_powerbi_windows.ps1
  macOS:   bash scripts/start_chrome_powerbi.sh
  python scrapers/scrape_powerbi_wind_online.py

输出：data/xinshang/powerbi_online_merchants.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers.cdp_client import CDPError, connect_tab
from scrapers.powerbi_wind_js import POWERBI_WIND_HELPERS_JS

REPORT_URL = (
    "https://app.powerbi.com/reportEmbed"
    "?reportId=1a6f7a23-0fd5-44d8-a37f-8cef116b8ad9"
    "&autoAuth=true&ctid=7c792a97-2300-4444-aa97-172fed9b0501"
)
OUT = ROOT / "data" / "xinshang" / "powerbi_online_merchants.json"


def main() -> int:
    try:
        session = connect_tab(9222, ["app.powerbi.com", "reportEmbed"])
    except CDPError as exc:
        print("[BAD] " + str(exc))
        print("Windows: powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\start_chrome_powerbi_windows.ps1")
        print("Then login in that Chrome: qiaoxh@ppu.powerbi.bi")
        return 1
    session.navigate(REPORT_URL)
    session.wait_ready(timeout=90)
    session.evaluate(POWERBI_WIND_HELPERS_JS)
    payload = session.evaluate("return await window.__CZ_PBI_WIND.scrapeOnlineMerchants();")
    if not payload or not payload.get("ok"):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    payload["source"] = "业务数据风向看板"
    payload["reportId"] = "1a6f7a23-0fd5-44d8-a37f-8cef116b8ad9"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {OUT} date={payload.get('date')} cities={payload.get('cities')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
