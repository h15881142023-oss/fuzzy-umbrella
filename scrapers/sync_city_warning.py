"""腾讯文档城市警告同步骨架。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from scrapers._common import write_status


def main() -> int:
    db.init_db()
    msg = "tencent city_warning 未配置。请用 Excel「城市警告」导入。"
    db.log_sync("sync_city_warning", "skip", msg)
    write_status("sync_city_warning", {"ok": True, "skipped": True, "message": msg})
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
