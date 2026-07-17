#!/usr/bin/env python3
"""拜访检核日更：消费 Cloud Agent 工作区中的后台导出 Excel，入库（不写本机 Downloads）。

推荐由 Cursor Cloud Agent 定时执行：
1) 在云端浏览器打开后台拜访页（区域=川藏一区，拜访时间=昨天）
2) 等待表格刷新后点击导出，文件落到云端工作区 VISIT_EXPORT_DIR
3) 本脚本解析最新 xlsx → 检核 → 写入本地/隧道可达的平台库
   或 --push-api 将 payload POST 到线上 /api/visit_check/import
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import PUBLIC_ORIGIN, SITE_PASSWORD, VISIT_EXPORT_DIR
from scrapers.import_visit_check import import_payload, load_payload
from scrapers.visit_admin_excel import excel_to_payload


def latest_xlsx(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def push_api(payload: dict, origin: str, password: str) -> dict:
    import urllib.error
    import urllib.request

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{origin.rstrip('/')}/api/visit_check/import",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-CZ-Token": password,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API {e.code}: {detail}") from e


def main() -> int:
    parser = argparse.ArgumentParser(description="拜访检核日更（后台 Excel）")
    parser.add_argument("--file", type=Path, help="指定 xlsx/json；默认取 VISIT_EXPORT_DIR 最新 xlsx")
    parser.add_argument("--export-dir", type=Path, default=VISIT_EXPORT_DIR)
    parser.add_argument("--push-api", action="store_true", help="推送到线上 API（适合 Cloud Agent）")
    parser.add_argument("--origin", default=os.environ.get("CZ_PUBLIC_ORIGIN", PUBLIC_ORIGIN))
    parser.add_argument("--token", default=os.environ.get("CZ_SITE_PASSWORD", SITE_PASSWORD))
    parser.add_argument("--keep", action="store_true", help="推送成功后保留云端 xlsx（默认删除）")
    args = parser.parse_args()

    path = args.file
    if path is None:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        path = latest_xlsx(args.export_dir)
        if path is None:
            print(f"未找到导出文件: {args.export_dir}", file=sys.stderr)
            return 1

    payload = load_payload(path) if path.suffix.lower() == ".json" else excel_to_payload(path)

    if args.push_api:
        out = push_api(payload, args.origin, args.token)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("ok") and not args.keep and path.suffix.lower() in {".xlsx", ".xlsm"}:
            path.unlink(missing_ok=True)
            print(f"已删除云端导出: {path}")
        return 0 if out.get("ok") else 1

    out = import_payload(payload)
    print(json.dumps({"ok": True, "rows": out["rows"], "region": out["region"], "check_date": out["check_date"]}, ensure_ascii=False, indent=2))
    for c in out["cities"]:
        print(
            f"- {c['city']}: {c['status']} BD {c['bd_compliant']}/{c['bd_total']} "
            f"拜访 {c['visit_compliant']}/{c['visit_total']}"
        )
    if not args.keep and path.suffix.lower() in {".xlsx", ".xlsm"}:
        # 本机跑时也避免长期留盘；Cloud 同理
        path.unlink(missing_ok=True)
        print(f"已删除导出文件: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
