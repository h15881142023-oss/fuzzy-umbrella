#!/usr/bin/env python3
"""将后台导出的拜访 Excel（或中间 JSON）检核后写入 visit_check_daily。

默认数据源：外卖陪访拜访看板后台导出，不再使用金山文档。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from scrapers._common import now, write_status
from scrapers.visit_admin_excel import excel_to_payload
from scrapers.visit_check import check_payload


def save_result(result: dict) -> int:
    ts = now()
    check_date = result["check_date"]
    rows = []
    for c in result["cities"]:
        rows.append(
            (
                check_date,
                c["city"],
                1 if c.get("has_data") else 0,
                c.get("status"),
                c.get("bd_total") or 0,
                c.get("bd_compliant") or 0,
                c.get("bd_rate") or 0,
                c.get("visit_total") or 0,
                c.get("visit_compliant") or 0,
                c.get("visit_rate") or 0,
                c.get("coop_count") or 0,
                c.get("noncoop_count") or 0,
                json.dumps(
                    {"bds": c.get("bds") or [], "issues": c.get("issues") or [], "sheet": c.get("sheet")},
                    ensure_ascii=False,
                ),
                ts,
            )
        )
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM visit_check_daily WHERE check_date=?", (check_date,))
    return db.upsert_many(
        """INSERT OR REPLACE INTO visit_check_daily
           (check_date, city, has_data, status, bd_total, bd_compliant, bd_rate,
            visit_total, visit_compliant, visit_rate, coop_count, noncoop_count, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def load_payload(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return excel_to_payload(path)
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"不支持的文件类型: {path}")


def import_payload(payload: dict) -> dict:
    result = check_payload(payload)
    n = save_result(result)
    write_status("visit_check", {"ok": True, "rows": n, "region": result["region"], "source": payload.get("source")})
    db.log_sync("visit_check", "ok", f"{result['check_date']} 写入 {n} 城 source={payload.get('source') or 'json'}")
    return {"ok": True, "rows": n, "region": result["region"], "cities": result["cities"], "check_date": result["check_date"]}


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "")
    if not path or not path.exists():
        print("用法: python scrapers/import_visit_check.py <导出.xlsx|payload.json>", file=sys.stderr)
        return 2
    out = import_payload(load_payload(path))
    print(json.dumps({"ok": True, "rows": out["rows"], "region": out["region"], "check_date": out["check_date"]}, ensure_ascii=False, indent=2))
    for c in out["cities"]:
        print(
            f"- {c['city']}: {c['status']} BD {c['bd_compliant']}/{c['bd_total']} "
            f"拜访 {c['visit_compliant']}/{c['visit_total']} 问题 {len(c.get('issues') or [])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
