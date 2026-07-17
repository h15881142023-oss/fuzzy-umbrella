"""将浏览器抓取的 Power BI sections JSON 写入 powerbi_delivery_rows。

默认：同 snapshot_date + city 已存在则跳过，不覆盖历史。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from config import normalize_city
from scrapers._common import now


def _to_num(raw: str) -> float | None:
    s = (raw or "").strip().replace(",", "").replace("%", "").replace("其他条件格式", "")
    if not s or s in {"-", "--", "null", "None"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _clean_text(raw: str) -> str:
    return (raw or "").replace("其他条件格式", "").strip()


def parse_page_date(raw: str | None) -> str | None:
    """接受 2026/7/15 或 2026-07-15，返回 YYYY-MM-DD。"""
    if not raw:
        return None
    s = str(raw).strip()
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def city_date_exists(snapshot_date: str, city: str) -> bool:
    row = db.query_one(
        "SELECT 1 AS x FROM powerbi_delivery_rows WHERE snapshot_date=? AND city=? LIMIT 1",
        (snapshot_date, city),
    )
    return bool(row)


def import_payload(
    payload: dict,
    snapshot_date: str | None = None,
    *,
    overwrite: bool = False,
) -> dict:
    d = parse_page_date(snapshot_date) or parse_page_date(payload.get("page_date")) or parse_page_date(
        payload.get("page_date_raw")
    )
    if not d:
        raise ValueError("缺少页面日期 page_date，拒绝用本机今天冒充")

    ts = now()
    city = normalize_city(payload.get("city")) or ""
    area = (payload.get("area") or "川藏一区").strip()
    if not city:
        raise ValueError("payload.city 缺失")

    db.init_db()
    if city_date_exists(d, city) and not overwrite:
        msg = f"{area}/{city}/{d}: 已存在，跳过不覆盖"
        db.log_sync("import_powerbi_browser", "ok", msg)
        return {
            "ok": True,
            "city": city,
            "date": d,
            "skipped_existing": True,
            "deleted": 0,
            "upsert": 0,
            "skipped": 0,
        }

    deleted = 0
    if overwrite:
        with db.connect() as conn:
            cur = conn.execute(
                "DELETE FROM powerbi_delivery_rows WHERE snapshot_date=? AND city=?",
                (d, city),
            )
            deleted = cur.rowcount

    rows_out: list[tuple] = []
    skipped = 0
    for sec in payload.get("sections") or []:
        section = (sec.get("section") or "").strip()
        headers = [h.strip() for h in (sec.get("headers") or [])]
        for r in sec.get("rows") or []:
            if not r or len(r) < 2:
                skipped += 1
                continue
            first = (r[0] or "").strip()
            if first in {"行选择", "活动大类"}:
                skipped += 1
                continue
            if first in {"总计", "合计"}:
                row_name, is_total, values = first, 1, r[1:]
                metric_headers = headers[2:] if len(headers) >= 2 else []
            elif first in {"选择行", "行选择"}:
                row_name = (r[1] or "").strip()
                if not row_name or row_name == "活动大类":
                    skipped += 1
                    continue
                is_total, values = 0, r[2:]
                metric_headers = headers[2:] if len(headers) >= 2 else []
                if len(values) < 2:
                    skipped += 1
                    continue
            else:
                row_name, is_total, values = first, int(first in {"总计", "合计"}), r[1:]
                metric_headers = headers[1:] if headers else []

            for i, cell in enumerate(values):
                metric_key = (
                    metric_headers[i]
                    if i < len(metric_headers) and metric_headers[i]
                    else f"col_{i + 1}"
                )
                if metric_key in {"行选择", "活动大类"}:
                    continue
                text = _clean_text(str(cell))
                rows_out.append(
                    (
                        d,
                        city,
                        area,
                        section,
                        row_name,
                        metric_key,
                        text,
                        _to_num(text),
                        is_total,
                        json.dumps({"headers": headers, "raw_row": r}, ensure_ascii=False),
                        ts,
                    )
                )

    n = db.upsert_many(
        """INSERT OR REPLACE INTO powerbi_delivery_rows
           (snapshot_date, city, area, section, row_name, metric_key, metric_text, metric_value, is_total, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows_out,
    )
    msg = f"{area}/{city}/{d}: deleted={deleted}, upsert={n}, skipped={skipped}, overwrite={overwrite}"
    db.log_sync("import_powerbi_browser", "ok", msg)
    return {
        "ok": True,
        "city": city,
        "date": d,
        "skipped_existing": False,
        "deleted": deleted,
        "upsert": n,
        "skipped": skipped,
    }


if __name__ == "__main__":
    path = Path(sys.argv[1])
    overwrite = "--overwrite" in sys.argv
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(import_payload(payload, overwrite=overwrite))
