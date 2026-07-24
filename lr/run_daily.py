#!/usr/bin/env python3
"""川藏一区 LR 日报：网页抓取 JSON → 填模板 → WPS 五城看板截图 → 企业微信（只推图+Excel）。

用法：
  python lr/run_daily.py --scrape-json data/lr_scrape/latest.json --target-date 2026-07-22
  python lr/run_daily.py --scrape-json sample.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Windows 控制台/管道避免中文 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
sys.path.insert(0, str(BASE))

from config import CITIES, LR_DIR, LR_TEMPLATE_DEFAULT, LR_WECOM_WEBHOOK, REGION_NAME  # noqa: E402
from lr.fill_template import fill_template  # noqa: E402
from lr.kanban_image import export_kanban_pngs  # noqa: E402
from lr.table_utils import filter_target_date, parse_scrape_payload  # noqa: E402
from lr.wecom_push import push_lr_report  # noqa: E402

DEFAULT_TEMPLATE = Path(os.environ.get("LR_TEMPLATE_PATH", LR_TEMPLATE_DEFAULT))
WORK_DIR = LR_DIR / "work"
OUTPUT_DIR = LR_DIR / "output"
DEFAULT_WEBHOOK = os.environ.get("LR_WECOM_WEBHOOK", LR_WECOM_WEBHOOK)


def load_scrape(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="LR 日报：抓取 JSON → 填表 → 推送")
    parser.add_argument("--scrape-json", type=Path, required=True, help="浏览器抓取的 headers/rows JSON")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--target-date", help="YYYY-MM-DD，默认昨天")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK)
    parser.add_argument("--dry-run", action="store_true", help="只生成文件，不推送企微")
    parser.add_argument(
        "--pillow-fallback",
        action="store_true",
        help="非 Windows 时允许 Pillow 占位图（调试用，非真实看板样式）",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="只填 Excel、不截图（云端无 WPS 时可用）",
    )
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

    print(f"[lr] fill template -> {WORK_DIR} target={target}", flush=True)
    filled = fill_template(args.template, rows, target, WORK_DIR)
    print(f"[lr] filled: {filled}", flush=True)

    pngs: list[Path] = []
    if not args.skip_images:
        allow_pillow = args.pillow_fallback or os.environ.get("LR_ALLOW_PILLOW") == "1"
        try:
            print("[lr] export kanban pngs (WPS/Excel) ...", flush=True)
            pngs = export_kanban_pngs(
                filled,
                OUTPUT_DIR,
                target,
                list(CITIES),
                allow_pillow_fallback=allow_pillow,
            )
            print(f"[lr] pngs: {[str(p) for p in pngs]}", flush=True)
        except Exception as exc:
            print(f"看板截图失败: {exc}", file=sys.stderr, flush=True)
            traceback.print_exc()
            if not args.dry_run:
                return 1
            print("dry-run 下继续（无 PNG）", file=sys.stderr, flush=True)

    summary = {
        "target_date": target.isoformat(),
        "cities": sorted({str(r.get("组织结构")) for r in rows}),
        "xlsx": str(filled),
        "pngs": [str(p) for p in pngs],
        "rows": len(rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if args.dry_run:
        print("dry-run: 跳过企业微信推送", flush=True)
        return 0

    if not pngs:
        print("无看板图片，拒绝推送（避免只发残缺消息）", file=sys.stderr, flush=True)
        return 1

    print("[lr] push wecom ...", flush=True)
    push_lr_report(args.webhook, pngs=pngs, xlsx=filled)
    print("企业微信推送成功（仅图片+Excel）", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
