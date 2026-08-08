#!/usr/bin/env python3
"""川藏一区「利润填写推送」：抓取 JSON → 填模板 → WPS 五城看板 → 企微（5 图+Excel）。

注意：本脚本 ≠「利润数据源推送」（见 lr/run_datasource_push.py）。

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
from lr.table_utils import filter_target_date, parse_scrape_payload  # noqa: E402
# kanban_image / wecom_push 仅在导出或推送时导入，避免本机旧文件阻断 --fill-only

DEFAULT_TEMPLATE = Path(os.environ.get("LR_TEMPLATE_PATH", LR_TEMPLATE_DEFAULT))
WORK_DIR = LR_DIR / "work"
OUTPUT_DIR = LR_DIR / "output"
DEFAULT_WEBHOOK = os.environ.get("LR_WECOM_WEBHOOK", LR_WECOM_WEBHOOK)
FILL_MARKER = WORK_DIR / "last_filled.json"


def _write_fill_marker(filled: Path, target: date) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    FILL_MARKER.write_text(
        json.dumps(
            {"target_date": target.isoformat(), "xlsx": str(filled.resolve())},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_scrape(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="LR 日报：抓取 JSON → 填表 → 推送")
    parser.add_argument("--scrape-json", type=Path, help="浏览器抓取的 headers/rows JSON")
    parser.add_argument(
        "--filled-xlsx",
        type=Path,
        help="已填好的 LR 日报 xlsx（跳过抓取填表，只导出看板+推送）",
    )
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
    parser.add_argument(
        "--fill-only",
        action="store_true",
        help="只抓取填表，不导出看板、不推送",
    )
    parser.add_argument(
        "--push-only",
        action="store_true",
        help="只企微推送（需 --filled-xlsx，且 lr/output 下已有五城 PNG）",
    )
    args = parser.parse_args()

    if args.push_only and not args.filled_xlsx:
        print("push-only 需要 --filled-xlsx", file=sys.stderr)
        return 1
    if args.fill_only and args.push_only:
        print("不能同时 --fill-only 与 --push-only", file=sys.stderr)
        return 1

    target = (
        datetime.strptime(args.target_date, "%Y-%m-%d").date()
        if args.target_date
        else date.today() - timedelta(days=1)
    )

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filled: Path
    rows: list = []
    if args.filled_xlsx:
        filled = args.filled_xlsx
        if not filled.exists():
            print(f"filled xlsx 不存在: {filled}", file=sys.stderr)
            return 1
        print(f"[lr] reuse filled xlsx: {filled} target={target}", flush=True)
    elif args.push_only:
        print("push-only 需要 --filled-xlsx", file=sys.stderr)
        return 1
    else:
        if not args.scrape_json:
            print("需要 --scrape-json 或 --filled-xlsx", file=sys.stderr)
            return 1
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

        print(f"[lr] fill template -> {WORK_DIR} target={target}", flush=True)
        filled = fill_template(args.template, rows, target, WORK_DIR)
        print(f"[lr] filled: {filled}", flush=True)
        _write_fill_marker(filled, target)
        # fill-only 跳过二次打开大表统计；避免 read_only 随机访问导致“假死”
        if not args.fill_only:
            try:
                from lr.fill_template import count_filled_days

                n_days = count_filled_days(filled)
                print(f"[lr] workbook days in 数据源(日): {n_days}", flush=True)
            except Exception as exc:
                print(f"[lr] count_filled_days skip: {exc}", flush=True)

    if args.fill_only:
        summary = {
            "target_date": target.isoformat(),
            "xlsx": str(filled),
            "mode": "fill-only",
            "cities": sorted({str(r.get("组织结构")) for r in rows}),
            "rows": len(rows),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 0

    pngs: list[Path] = []
    if args.push_only:
        for city in CITIES:
            safe = "".join("_" if c in '\\/:*?"<>|' else c for c in city)
            cand = OUTPUT_DIR / f"看板-单城_{safe}_{target.month}.png"
            if not cand.exists():
                print(f"push-only 缺少 PNG: {cand}", file=sys.stderr)
                return 1
            pngs.append(cand)
        print(f"[lr] push-only pngs: {[str(p) for p in pngs]}", flush=True)
    elif not args.skip_images:
        from lr.kanban_image import export_kanban_pngs

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
        "xlsx": str(filled),
        "pngs": [str(p) for p in pngs],
    }
    if not args.filled_xlsx:
        summary["cities"] = sorted({str(r.get("组织结构")) for r in rows})
        summary["rows"] = len(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if args.dry_run:
        print("dry-run: 跳过企业微信推送", flush=True)
        return 0

    if not pngs:
        print("无看板图片，拒绝推送（避免只发残缺消息）", file=sys.stderr, flush=True)
        return 1

    from lr.wecom_push import push_lr_report

    print("[lr] push wecom (5 images + excel) ...", flush=True)
    result = push_lr_report(args.webhook, pngs=pngs, xlsx=filled)
    print(json.dumps({"wecom": {"image_count": result.get("image_count"), "file": result.get("file")}}, ensure_ascii=False), flush=True)
    print("企业微信推送成功（5图+Excel）", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
