#!/usr/bin/env python3
"""川藏一区 KPI 待办进度：网页抓取 JSON → 表格图片 → 企业微信。

Cloud Agent 推荐流程：
1. 登录后台，打开 KPI 待办页，筛选区域=川藏一区、周期=本月
2. 抓取表格 headers/rows，保存 JSON
3. 本脚本生成标红图片并推送企微

用法：
  python kpi_todo/run_biweekly.py --scrape-json data/kpi_todo_scrape/latest.json
  python kpi_todo/run_biweekly.py --notify-only --message "抓取失败：无数据"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
sys.path.insert(0, str(BASE))

from config import KPI_TODO_DIR, REGION_NAME  # noqa: E402
from kpi_todo.table_image import render_table_png  # noqa: E402
from kpi_todo.table_utils import (  # noqa: E402
    EXPECTED_HEADERS,
    count_incomplete,
    latest_update_date,
    parse_scrape_payload,
    rows_for_table,
)
from kpi_todo.wecom_push import push_markdown, push_report  # noqa: E402

DEFAULT_WEBHOOK = os.environ.get(
    "WECOM_WEBHOOK",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb",
)
SCRAPE_DIR = KPI_TODO_DIR / "scrape"
OUTPUT_DIR = KPI_TODO_DIR / "output"


def detect_non_target_regions(payload: dict) -> list[str]:
    headers = payload.get("headers") or []
    rows = payload.get("rows") or []
    idx = None
    for i, h in enumerate(headers):
        hs = str(h or "").strip()
        if hs in {"区域", "区域名称"}:
            idx = i
            break
    if idx is None:
        return []
    regions = set()
    for row in rows:
        if not isinstance(row, list) or idx >= len(row):
            continue
        val = str(row[idx] or "").strip()
        if val and val != REGION_NAME:
            regions.add(val)
    return sorted(regions)


def build_summary(rows: list[dict], cutoff: date | None) -> str:
    incomplete = count_incomplete(rows)
    cutoff_text = cutoff.isoformat() if cutoff else date.today().isoformat()
    if incomplete == 0:
        status = f"截止 **{cutoff_text}** todo **均达成**"
    else:
        status = f"截止 **{cutoff_text}** 有 **{incomplete}** 项 todo 未达成（红色格=1项）"
    return (
        f"## 📋 川藏一区 KPI 待办进度\n\n"
        f"- 区域：{REGION_NAME}\n"
        f"- 周期：本月\n"
        f"- 数据行数：{len(rows)}\n"
        f"- {status}"
    )


def notify_text(webhook: str, message: str) -> dict:
    content = f"## ⚠️ 川藏一区 KPI 待办进度\n\n{message}"
    return push_markdown(webhook, content)


def main() -> int:
    parser = argparse.ArgumentParser(description="KPI 待办进度：抓取 JSON → 图片 → 企微")
    parser.add_argument("--scrape-json", type=Path, help="浏览器抓取的 headers/rows JSON")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK)
    parser.add_argument("--dry-run", action="store_true", help="只生成图片，不推送企微")
    parser.add_argument("--notify-only", action="store_true", help="仅推送文字说明（失败/无数据）")
    parser.add_argument("--message", help="配合 --notify-only 的说明文字")
    args = parser.parse_args()

    if args.notify_only:
        msg = args.message or "任务执行失败，未生成表格图片。"
        resp = notify_text(args.webhook, msg)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0 if resp.get("errcode") == 0 else 1

    if not args.scrape_json or not args.scrape_json.exists():
        msg = f"抓取文件不存在：{args.scrape_json}"
        print(msg, file=sys.stderr)
        if not args.dry_run:
            notify_text(args.webhook, msg)
        return 1

    payload = json.loads(args.scrape_json.read_text(encoding="utf-8"))
    bad_regions = detect_non_target_regions(payload)
    if bad_regions:
        msg = (
            "筛选校验失败：抓取结果包含非目标区域 "
            f"{', '.join(bad_regions)}；已停止出图推送。"
        )
        print(msg, file=sys.stderr)
        if not args.dry_run:
            notify_text(args.webhook, msg)
        return 1
    rows = parse_scrape_payload(payload)
    if not rows:
        msg = "筛选后无数据（请确认区域=川藏一区、周期=本月，且表格已刷新）。"
        print(msg, file=sys.stderr)
        if not args.dry_run:
            notify_text(args.webhook, msg)
        return 1

    cutoff = latest_update_date(rows) or date.today()
    table_rows = rows_for_table(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUTPUT_DIR / f"kpi_todo_{cutoff.isoformat()}.png"
    render_table_png(
        EXPECTED_HEADERS,
        table_rows,
        raw_rows=rows,
        out_png=png_path,
    )

    summary = {
        "cutoff_date": cutoff.isoformat(),
        "rows": len(rows),
        "incomplete": count_incomplete(rows),
        "png": str(png_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.dry_run:
        print("dry-run: 跳过企业微信推送")
        return 0

    title = build_summary(rows, cutoff)
    push_report(args.webhook, title=title, png=png_path)
    print("企业微信推送成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
