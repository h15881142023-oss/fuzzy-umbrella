#!/usr/bin/env python3
"""嗅探美团看板页面的 XHR 接口，帮助填写 meituan_endpoints.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers.cdp_client import CDPError, connect_tab
from scrapers.meituan_config import CHROME_CDP_PORT, ENDPOINTS_FILE, TAB_URL_PATTERNS, load_endpoints


def main() -> int:
    cfg = load_endpoints()
    page = cfg.get("pages", {}).get("dashboard", "https://igate.waimai.meituan.com/")
    try:
        session = connect_tab(CHROME_CDP_PORT, TAB_URL_PATTERNS)
    except CDPError as exc:
        print(exc)
        print("请先运行: bash scripts/start_chrome_meituan.sh")
        return 1
    try:
        session.navigate(page, wait_sec=2.0)
        keywords = []
        for vals in (cfg.get("network_keywords") or {}).values():
            keywords.extend(vals)
        keywords = list(dict.fromkeys(keywords))

        def match(url: str) -> bool:
            u = url.lower()
            return any(k.lower() in u for k in keywords) or "api" in u or "gw/" in u

        captured = session.capture_responses(match, duration_sec=20.0, reload=True)
        urls = []
        for item in captured:
            try:
                data = json.loads(item.body)
                preview = "json"
            except json.JSONDecodeError:
                preview = "text"
            urls.append({"url": item.url, "type": preview, "size": len(item.body)})
        out = ROOT / "scrapers" / "_last_runs" / "discovered_apis.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"page": page, "apis": urls}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"发现 {len(urls)} 个接口，已保存: {out}")
        for u in urls[:30]:
            print(f"  - [{u['type']}] {u['url']}")
        if urls:
            print("\n把需要的完整 URL 复制到 scrapers/meituan_endpoints.json 的 api_fetch_urls 数组")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
