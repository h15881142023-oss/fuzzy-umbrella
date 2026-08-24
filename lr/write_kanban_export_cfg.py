#!/usr/bin/env python3
"""Write UTF-8 JSON for WPS kanban export (keeps Chinese out of PS1 files)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import CITIES, REGION_NAME  # noqa: E402

KANBAN_SHEET = "看板-单城"
RANGE = "B1:R37"
PNG_PREFIX = "看板-单城"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--target-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--config", required=True, help="output JSON path")
    args = ap.parse_args()

    xlsx = Path(args.xlsx).resolve()
    if not xlsx.exists():
        print(f"xlsx not found: {xlsx}", file=sys.stderr)
        return 1

    target = datetime.strptime(args.target_date, "%Y-%m-%d").date()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        "xlsx": str(xlsx),
        "outDir": str(out_dir),
        "month": target.month,
        "region": REGION_NAME,
        "cities": list(CITIES),
        "sheet": KANBAN_SHEET,
        "range": RANGE,
        "pngPrefix": PNG_PREFIX,
        "expectedCount": len(CITIES),
    }
    cfg_path = Path(args.config)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(cfg_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
