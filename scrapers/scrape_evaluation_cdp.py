"""合作商评价体系抓取骨架。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from scrapers._common import write_status


def main() -> int:
    db.init_db()
    msg = "evaluation CDP 未配置。请将含 partner_name 的表放入「经营管理」或补齐抓取。"
    db.log_sync("scrape_evaluation_cdp", "skip", msg)
    write_status("scrape_evaluation_cdp", {"ok": True, "skipped": True, "message": msg})
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
