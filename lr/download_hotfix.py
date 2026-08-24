#!/usr/bin/env python3
"""Download local-automation scripts as raw bytes (encoding-safe on GBK Windows)."""
from __future__ import annotations

import sys
import urllib.error
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
    "lr/prepare_kanban_city.py",
    "lr/verify_kanban_pngs.py",
    "lr/kanban_image.py",
    "lr/export_kanban_com.py",
    "lr/wecom_push.py",
    "lr/run_daily.py",
    "lr/scrape_live.py",
    "lr/download_hotfix.py",
    "config.py",
    # shared + runners
    "scripts/_local_common.ps1",
    "scripts/export_lr_kanban_wps.ps1",
    "scripts/run_lr_kanban_export.ps1",
    "scripts/run_lr_kanban_push_existing.ps1",
    "scripts/install_lr_new_template.ps1",
    "scripts/uninstall_lr_datasource_task.ps1",
    "scripts/run_store_morning_monitor_local.ps1",
    "scripts/start_chrome_powerbi.ps1",
    "scripts/run_visit_check_local.ps1",
    "scripts/run_kpi_todo_local.ps1",
    "scripts/install_local_automations_windows.ps1",
]

# 已删除任务：拉 hotfix 时顺带清掉本机残留
OBSOLETE = [
    "scripts/run_lr_datasource_local.ps1",
    "lr/run_datasource_push.py",
    "scripts/run_lr_profit_fill_local.ps1",
    "scripts/run_lr_profit_fill_backfill.ps1",
    "scripts/install_lr_profit_fill_once.ps1",
    "scripts/run_lr_daily_local.ps1",
    "scripts/run_aug_tuangou_once.ps1",
]


def _mirrors(sha: str, rel: str) -> list[str]:
    path = rel.replace("\\", "/")
    return [
        f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{sha}/{path}",
        f"https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/{sha}/{path}",
    ]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fuzzy-umbrella-hotfix/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if len(data) < 40:
        raise RuntimeError(f"download too short: {url}")
    return data


def fetch_first(sha: str, rel: str) -> bytes | None:
    last_err: Exception | None = None
    for url in _mirrors(sha, rel):
        try:
            return fetch(url)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 404:
                continue
            last_err = exc
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if last_err is not None and getattr(last_err, "code", None) == 404:
        return None
    if last_err is not None:
        raise last_err
    return None


def main() -> int:
    global SHA, BASE
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("ERROR: pass commit SHA, e.g. python lr/download_hotfix.py abc1234", file=sys.stderr)
        return 2
    SHA = sys.argv[1].strip()
    if SHA.upper() == "HEAD":
        print("ERROR: refuse SHA=HEAD (would pull stale main). Pass a branch short SHA.", file=sys.stderr)
        return 2
    if len(SHA) > 7 and not SHA.startswith("cursor/"):
        SHA = SHA[:7]
    BASE = f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{SHA}"

    ok = 0
    skipped = 0
    for rel in FILES:
        out = ROOT / rel.replace("/", "\\") if sys.platform == "win32" else ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        data = fetch_first(SHA, rel)
        if data is None:
            print(f"SKIP 404 {rel} (removed upstream or CDN lag)")
            skipped += 1
            continue
        out.write_bytes(data)
        print(f"OK {out} ({len(data)} bytes)")
        ok += 1

    for rel in OBSOLETE:
        p = ROOT / rel.replace("/", "\\") if sys.platform == "win32" else ROOT / rel
        if p.exists():
            p.unlink()
            print(f"REMOVED obsolete {p}")

    required = [
        "scripts/run_store_morning_monitor_local.ps1",
        "scripts/run_visit_check_local.ps1",
        "scripts/run_kpi_todo_local.ps1",
        "lr/fill_template.py",
        "lr/prepare_kanban_city.py",
        "config.py",
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

    cfg = ROOT / "config.py"
    ctext = cfg.read_text(encoding="utf-8", errors="replace")
    if "ADMIN_PASSWORD" not in ctext or "ADMIN_USER" not in ctext:
        print("ERROR: config.py missing ADMIN_USER/ADMIN_PASSWORD. Abort.", file=sys.stderr)
        return 2
    if "LR_ADMIN_URL" not in ctext or "chuxin.city" not in ctext:
        print("ERROR: config.py missing LR chuxin.city admin URL. Abort.", file=sys.stderr)
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

    wps = ROOT / ("scripts\\export_lr_kanban_wps.ps1" if win else "scripts/export_lr_kanban_wps.ps1")
    wtext = wps.read_text(encoding="utf-8", errors="replace")
    if "Invoke-ComNoOut" not in wtext or "Workbooks.Open($xlsx)" not in wtext:
        print("ERROR: export_lr_kanban_wps.ps1 missing COM cast fix. Abort.", file=sys.stderr)
        return 2
    if "skipCellWrites" not in wtext or "skip COM cell writes" not in wtext:
        print("ERROR: export_lr_kanban_wps.ps1 must skip COM cell writes. Abort.", file=sys.stderr)
        return 2
    if 'Range("E3").Value2' in wtext or ".Value2 = $Region" in wtext:
        print("ERROR: export_lr_kanban_wps.ps1 still writes text via Value2. Abort.", file=sys.stderr)
        return 2
    if "CopyPicture(" in wtext and "| Out-Null" in wtext.split("function Export-RangePng")[-1].split("if (-not (Test-Path")[0]:
        print("ERROR: export_lr_kanban_wps.ps1 still pipes CopyPicture to Out-Null. Abort.", file=sys.stderr)
        return 2

    prep = ROOT / ("lr\\prepare_kanban_city.py" if win else "lr/prepare_kanban_city.py")
    if not prep.exists():
        print("ERROR: missing lr/prepare_kanban_city.py. Abort.", file=sys.stderr)
        return 2
    ptext = prep.read_text(encoding="utf-8", errors="replace")
    if 'ws["C3"]' not in ptext or "skipCellWrites" not in ptext:
        print("ERROR: prepare_kanban_city.py missing openpyxl C3 / skipCellWrites. Abort.", file=sys.stderr)
        return 2

    exp = ROOT / ("scripts\\run_lr_kanban_export.ps1" if win else "scripts/run_lr_kanban_export.ps1")
    etext = exp.read_text(encoding="utf-8", errors="replace")
    if "prepare_kanban_city.py" not in etext:
        print("ERROR: run_lr_kanban_export.ps1 must call prepare_kanban_city.py. Abort.", file=sys.stderr)
        return 2

    print(f"done {ok} files from {BASE} (skipped={skipped})")
    print("OK all required local runners present")
    print("OK fill_template.py has cumulative fill")
    print("OK fill_template.py has 团购利润 fill")
    print("OK config.py has ADMIN_PASSWORD + chuxin LR URL")
    print("OK kanban_image.py has export_kanban_pngs")
    print("OK run_daily.py lazy-imports kanban for fill-only")
    print("OK export_lr_kanban_wps.ps1 has COM cast fix")
    print("OK kanban filters via openpyxl; WPS screenshot only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
