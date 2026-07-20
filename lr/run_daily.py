#!/usr/bin/env python3
"""川藏一区 LR 日报：网页抓取 JSON → 填模板 → 看板截图 → 企业微信。

Cloud Agent 推荐流程：
1. 浏览器打开 LR 日利润表，筛选区域=川藏一区、日期=昨天
2. 直接抓取表格 headers/rows，保存 JSON
3. 本脚本消费 JSON，写入模板并推送

用法：
  python lr/run_daily.py --scrape-json data/lr_scrape/latest.json
  python lr/run_daily.py --scrape-json sample.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
sys.path.insert(0, str(BASE))

from config import LR_DIR, REGION_NAME  # noqa: E402
from lr.fill_template import fill_template  # noqa: E402
from lr.kanban_image import export_kanban_png  # noqa: E402
from lr.table_utils import filter_target_date, parse_scrape_payload  # noqa: E402
from lr.wecom_push import push_lr_report  # noqa: E402

DEFAULT_TEMPLATE = Path(
    os.environ.get(
        "LR_TEMPLATE_PATH",
        "/Users/qxh/月度工作/2026年/26年1月工作/LR日报总表模版5.4版(川藏一区) .xlsx",
    )
)
WORK_DIR = LR_DIR / "work"
OUTPUT_DIR = LR_DIR / "output"
DEFAULT_WEBHOOK = os.environ.get(
    "WECOM_WEBHOOK",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb",
)


def load_scrape(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="LR 日报：抓取 JSON → 填表 → 推送")
    parser.add_argument("--scrape-json", type=Path, required=True, help="浏览器抓取的 headers/rows JSON")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--target-date", help="YYYY-MM-DD，默认昨天")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK)
    parser.add_argument("--dry-run", action="store_true", help="只生成文件，不推送企微")
    args = parser.parse_args()

    target = (
        datetime.strptime(args.target_date, "%Y-%m-%d").date()
        if args.target_date
        else date.today() - timedelta(days=1)
    )

    if not args.template.exists():
        print(f"模板不存在: {args.template}", file=sys.stderr)
        return 1
    if not args.scrape_json.exists():
        print(f"抓取文件不存在: {args.scrape_json}", file=sys.stderr)
        return 1

    payload = load_scrape(args.scrape_json)
    rows_all = parse_scrape_payload(payload)
    rows = filter_target_date(rows_all, target)
    if not rows:
        print(
            f"未找到 {REGION_NAME} 五城在 {target} 的数据；"
            f"抓取共 {len(rows_all)} 行",
            file=sys.stderr,
        )
        return 1

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filled = fill_template(args.template, rows, target, WORK_DIR)
    png = export_kanban_png(filled, OUTPUT_DIR / f"看板-单城_{target.isoformat()}.png")

    summary = {
        "target_date": target.isoformat(),
        "cities": sorted({str(r.get("组织结构")) for r in rows}),
        "xlsx": str(filled),
        "png": str(png),
        "rows": len(rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.dry_run:
        print("dry-run: 跳过企业微信推送")
        return 0

    title = (
        f"## 📊 川藏一区 LR 日报（{target}）\n\n"
        f"- 区域：{REGION_NAME}\n"
        f"- 写入工作表：`数据源(日)`\n"
        f"- 城市：{', '.join(summary['cities'])}\n"
        f"- 附件：看板截图 + 填好数据的 Excel"
    )
    push_lr_report(args.webhook, title=title, png=png, xlsx=filled)
    print("企业微信推送成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
