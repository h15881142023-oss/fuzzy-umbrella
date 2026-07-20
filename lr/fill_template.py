"""将抓取结果写入 LR 模板「数据源(日)」。"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from config import CITIES, REGION_NAME
from lr.table_utils import norm_header
from lr.xlsx_sanitize import sanitize_for_openpyxl

DATA_SHEET = "数据源(日)"
HEADER_ROW = 3


def _header_col_map(ws) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        val = ws.cell(HEADER_ROW, col).value
        if val:
            mapping[norm_header(val)] = col
    return mapping


def _row_key(region: str, city: str, day: date) -> tuple[str, str, str]:
    return region, city, day.isoformat()


def _read_row_day(cell_val: Any) -> date | None:
    if isinstance(cell_val, datetime):
        return cell_val.date()
    if isinstance(cell_val, date):
        return cell_val
    if isinstance(cell_val, str):
        s = cell_val.strip()
        if s.startswith("="):
            return None
        if len(s) >= 10:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
    return None


def fill_template(
    template: Path,
    rows: list[dict[str, Any]],
    target: date,
    out_dir: Path,
) -> Path:
    """复制模板并写入昨天五城数据，返回输出路径。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"LR日报_{target.isoformat()}.xlsx"
    sanitize_for_openpyxl(template, out_path)

    wb = load_workbook(out_path)
    if DATA_SHEET not in wb.sheetnames:
        raise ValueError(f"模板缺少工作表: {DATA_SHEET}")
    ws = wb[DATA_SHEET]
    col_map = _header_col_map(ws)

    # 现有行索引：区域+城市+日
    index: dict[tuple[str, str, str], int] = {}
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        region = norm_header(ws.cell(r, col_map.get("区域", 1)).value)
        city = norm_header(ws.cell(r, col_map.get("组织结构", 2)).value)
        day = _read_row_day(ws.cell(r, col_map.get("日", 3)).value)
        if region and city and day:
            index[_row_key(region, city, day)] = r

    by_city = {str(r.get("组织结构")): r for r in rows if r.get("组织结构") in CITIES}
    missing = [c for c in CITIES if c not in by_city]
    if missing:
        raise ValueError(f"抓取数据缺少城市: {missing}；目标日={target}")

    next_row = ws.max_row + 1
    for city in CITIES:
        src = by_city[city]
        key = _row_key(REGION_NAME, city, target)
        row_idx = index.get(key, next_row)
        if row_idx == next_row:
            next_row += 1

        for header, val in src.items():
            col = col_map.get(norm_header(header))
            if not col:
                continue
            if header == "日":
                val = datetime.combine(target, datetime.min.time())
            ws.cell(row_idx, col, val)

    wb.save(out_path)
    wb.close()
    return out_path
