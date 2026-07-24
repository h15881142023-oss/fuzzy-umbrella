#!/usr/bin/env python3
"""利润数据源推送（独立任务，≠ 利润填写推送）。

只做：抓取 LR 日利润表 → 导出五城原始数据 Excel → 推送到数据源专用企微。
不做：LR 模板填写、WPS 看板截图。

用法：
  python lr/run_datasource_push.py --scrape-json data/lr_scrape/latest.json --target-date 2026-07-22
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
sys.path.insert(0, str(BASE))

from openpyxl import Workbook  # noqa: E402

from config import (  # noqa: E402
    CITIES,
    LR_DATASOURCE_WECOM_WEBHOOK,
    LR_DIR,
    REGION_NAME,
)
from lr.table_utils import filter_target_date, parse_scrape_payload  # noqa: E402
from lr.wecom_push import push_file  # noqa: E402

WORK_DIR = LR_DIR / "work" / "datasource"
DEFAULT_WEBHOOK = os.environ.get("LR_DATASOURCE_WECOM_WEBHOOK", LR_DATASOURCE_WECOM_WEBHOOK)

# 数据源推送导出的列（网页/模板常用字段）
EXPORT_COLUMNS = [
    "区域",
    "组织结构",
    "日",
    "原价交易额",
    "商品原价交易额",
    "餐盒费",
    "合作商补贴金额",
    "合作商补贴率 (页面代补率)",
    "全量订单",
    "专送订单量",
    "专送主板订单量",
    "专送PHF订单量",
    " 众包主板",
    " 众包PHF",
    "众包跑腿",
    " 高校订单",
    "活动补贴",
    "商家服务费",
    "专送配送费",
    "后台收入",
    "调账",
    "套补金额",
]


def _cell(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    return v


def write_datasource_xlsx(rows: list[dict], target: date, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"日利润数据源_{target.isoformat()}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "日利润数据源"
    ws.append(EXPORT_COLUMNS)
    by_city = {str(r.get("组织结构")): r for r in rows}
    for city in CITIES:
        src = by_city.get(city) or {}
        ws.append([_cell(src.get(col)) for col in EXPORT_COLUMNS])
    wb.save(out_path)
    wb.close()
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="利润数据源推送（仅原始表，不含填写/看板）")
    parser.add_argument("--scrape-json", type=Path, required=True)
    parser.add_argument("--target-date", help="YYYY-MM-DD，默认昨天")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = (
        datetime.strptime(args.target_date, "%Y-%m-%d").date()
        if args.target_date
        else date.today() - timedelta(days=1)
    )
    if not args.scrape_json.exists():
        print(f"抓取文件不存在: {args.scrape_json}", file=sys.stderr)
        return 1

    payload = json.loads(args.scrape_json.read_text(encoding="utf-8"))
    rows_all = parse_scrape_payload(payload)
    rows = filter_target_date(rows_all, target)
    if not rows:
        print(
            f"未找到 {REGION_NAME} 五城在 {target} 的数据；抓取共 {len(rows_all)} 行",
            file=sys.stderr,
        )
        return 1

    missing = [c for c in CITIES if c not in {str(r.get("组织结构")) for r in rows}]
    if missing:
        print(f"缺少城市: {missing}", file=sys.stderr)
        return 1

    xlsx = write_datasource_xlsx(rows, target, WORK_DIR)
    summary = {
        "task": "利润数据源推送",
        "target_date": target.isoformat(),
        "cities": list(CITIES),
        "xlsx": str(xlsx),
        "rows": len(rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if args.dry_run:
        print("dry-run: 跳过企微", flush=True)
        return 0

    print(f"[datasource] push file -> webhook ...", flush=True)
    push_file(args.webhook, xlsx)
    print("利润数据源推送成功（仅 Excel 文件）", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
