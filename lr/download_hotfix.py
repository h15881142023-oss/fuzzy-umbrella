#!/usr/bin/env python3
"""Download local-automation scripts as raw bytes (encoding-safe on GBK Windows)."""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "HEAD"
BASE = f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{SHA}"

FILES = [
    # core LR
    "lr/fill_template.py",
    "lr/table_utils.py",
    "lr/xlsx_sanitize.py",
    "lr/inspect_workbook_days.py",
    "lr/write_kanban_export_cfg.py",
    "lr/verify_kanban_pngs.py",
    "lr/kanban_image.py",
    "lr/export_kanban_com.py",
    "lr/wecom_push.py",
    "lr/run_daily.py",
    "lr/run_datasource_push.py",
    "lr/scrape_live.py",
    "lr/download_hotfix.py",
    "config.py",
    # shared + runners
    "scripts/_local_common.ps1",
    "scripts/export_lr_kanban_wps.ps1",
    "scripts/run_lr_kanban_export.ps1",
    "scripts/run_lr_kanban_push_existing.ps1",
    "scripts/run_lr_profit_fill_local.ps1",
    "scripts/run_lr_profit_fill_backfill.ps1",
    "scripts/install_lr_new_template.ps1",
    "scripts/run_lr_datasource_local.ps1",
    "scripts/run_store_morning_monitor_local.ps1",
    "scripts/start_chrome_powerbi.ps1",
    "scripts/run_visit_check_local.ps1",
    "scripts/run_kpi_todo_local.ps1",
    "scripts/install_local_automations_windows.ps1",
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fuzzy-umbrella-hotfix/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if len(data) < 40:
        raise RuntimeError(f"download too short: {url}")
    return data


def main() -> int:
    global SHA, BASE
    if len(sys.argv) > 1 and sys.argv[1].strip():
        SHA = sys.argv[1].strip()
        if len(SHA) > 7 and not SHA.startswith("cursor/"):
            SHA = SHA[:7]
        BASE = f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{SHA}"

    ok = 0
    for rel in FILES:
        url = f"{BASE}/{rel.replace(chr(92), '/')}"
        out = ROOT / rel.replace("/", "\\") if sys.platform == "win32" else ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        data = fetch(url)
        out.write_bytes(data)
        print(f"OK {out} ({len(data)} bytes)")
        ok += 1

    required = [
        "scripts/run_lr_datasource_local.ps1",
        "scripts/run_lr_profit_fill_local.ps1",
        "scripts/run_store_morning_monitor_local.ps1",
        "scripts/run_visit_check_local.ps1",
        "scripts/run_kpi_todo_local.ps1",
        "lr/fill_template.py",
    ]
    missing = []
    for rel in required:
        p = ROOT / rel.replace("/", "\\") if sys.platform == "win32" else ROOT / rel
        if not p.exists():
            missing.append(rel)
    if missing:
        print("ERROR missing after download: " + ", ".join(missing), file=sys.stderr)
        return 2

    win = sys.platform == "win32"
    fill = ROOT / ("lr\\fill_template.py" if win else "lr/fill_template.py")
    text = fill.read_text(encoding="utf-8", errors="replace")
    if "monthly_master_path" not in text or "_resolve_base_workbook" not in text:
        print("ERROR: fill_template.py is OLD (no cumulative fill). Abort.", file=sys.stderr)
        return 2
    if "_fill_tuangou_profit" not in text or "TUANGOU_DAILY_PROFIT" not in text:
        print("ERROR: fill_template.py missing 团购利润 fill. Abort.", file=sys.stderr)
        return 2

    kanban = ROOT / ("lr\\kanban_image.py" if win else "lr/kanban_image.py")
    ktext = kanban.read_text(encoding="utf-8", errors="replace")
    if "def export_kanban_pngs(" not in ktext:
        print("ERROR: kanban_image.py missing export_kanban_pngs. Abort.", file=sys.stderr)
        return 2

    daily = ROOT / ("lr\\run_daily.py" if win else "lr/run_daily.py")
    dtext = daily.read_text(encoding="utf-8", errors="replace")
    if "from lr.kanban_image import export_kanban_pngs" in dtext.split("def main")[0]:
        print("ERROR: run_daily.py still imports kanban_image at top-level. Abort.", file=sys.stderr)
        return 2

    print(f"done {ok} files from {BASE}")
    print("OK all required local runners present")
    print("OK fill_template.py has cumulative fill")
    print("OK fill_template.py has 团购利润 fill")
    print("OK kanban_image.py has export_kanban_pngs")
    print("OK run_daily.py lazy-imports kanban for fill-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
