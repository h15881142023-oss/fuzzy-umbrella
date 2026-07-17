"""经营管理 / 合作商评价 Excel 手动导入入口。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_sync import import_business
import db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("excel", type=Path)
    args = parser.parse_args()
    db.init_db()
    n = import_business(args.excel)
    print(f"imported {n} rows from {args.excel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
