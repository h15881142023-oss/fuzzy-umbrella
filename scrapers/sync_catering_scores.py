"""餐饮 KPI：优先读今日 dashboard 快照，否则走 CDP 抓取。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from scrapers._common import today, write_status
from scrapers.meituan_scraper import collect_payloads, save_kpi_scores
from scrapers.cdp_client import CDPError, connect_tab
from scrapers.meituan_config import CHROME_CDP_PORT, TAB_URL_PATTERNS, load_endpoints


def _from_snapshot(cfg) -> list:
    snap = db.query_one(
        "SELECT payload_json FROM dashboard_snapshots WHERE snapshot_date=?",
        (today(),),
    )
    if not snap:
        return []
    data = json.loads(snap["payload_json"])
    payloads = data.get("payloads") or []
    return payloads


def main() -> int:
    db.init_db()
    cfg = load_endpoints()
    keywords = (cfg.get("network_keywords") or {}).get("catering", [])
    payloads = _from_snapshot(cfg)
    logs = []
    if payloads:
        logs.append("使用今日 dashboard 快照")
    else:
        try:
            session = connect_tab(CHROME_CDP_PORT, TAB_URL_PATTERNS)
            try:
                payloads, logs = collect_payloads(session, "dashboard", keywords, cfg)
            finally:
                session.close()
        except CDPError as exc:
            msg = str(exc)
            write_status("sync_catering_scores", {"ok": False, "error": msg})
            db.log_sync("sync_catering_scores", "fail", msg)
            print(msg)
            return 1
    if not payloads:
        msg = "无餐饮 KPI 数据。请先运行 scrape_dashboard_cdp.py 或配置看板 URL"
        write_status("sync_catering_scores", {"ok": False, "message": msg})
        db.log_sync("sync_catering_scores", "fail", msg)
        print(msg)
        return 1
    n = save_kpi_scores(payloads, cfg, "catering")
    write_status("sync_catering_scores", {"ok": True, "rows": n, "logs": logs})
    db.log_sync("sync_catering_scores", "ok", f"写入 {n} 行")
    print(f"餐饮 KPI 写入 {n} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
