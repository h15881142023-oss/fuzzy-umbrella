"""KPI 待办：表头归一化、筛选、完成进度解析。"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from config import REGION_NAME

# 企微出图列（与后台一致的关键列；过长文本列不出图）
EXPECTED_HEADERS = [
    "考核开始",
    "考核结束",
    "合作城市",
    "渠道经理",
    "业务类型",
    "指标名称",
    "判断标准",
    "业务目标",
    "已完成",
    "完成进度",
    "考核状态",
    "更新日期",
]

HEADER_ALIASES: dict[str, str] = {
    "考核开始": "考核开始",
    "考核结束": "考核结束",
    "区域": "区域",
    "区域名称": "区域",
    "合作城市": "合作城市",
    "城市": "合作城市",
    "渠道经理": "渠道经理",
    "经理": "渠道经理",
    "业务类型": "业务类型",
    "指标类型": "指标类型",
    "指标名称": "指标名称",
    "判断标准": "判断标准",
    "业务目标": "业务目标",
    "已完成": "已完成",
    "完成进度": "完成进度",
    "考核状态": "考核状态",
    "更新日期": "更新日期",
}


def norm_header(name: Any) -> str:
    s = str(name or "").replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", s).strip()


def map_header(name: Any) -> str | None:
    key = norm_header(name)
    if key in HEADER_ALIASES:
        return HEADER_ALIASES[key]
    compact = key.replace(" ", "")
    for src, dst in HEADER_ALIASES.items():
        if src.replace(" ", "") == compact:
            return dst
    return key or None


def parse_progress(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        if v > 1 and v <= 100:
            return v / 100
        return v
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            return None
    try:
        v = float(s)
        if v > 1 and v <= 100:
            return v / 100
        return v
    except ValueError:
        return None


def parse_date_value(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            pass
    return None


def parse_scrape_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [map_header(h) for h in payload.get("headers") or []]
    rows_in = payload.get("rows") or []
    out: list[dict[str, Any]] = []

    for row in rows_in:
        mapped: dict[str, Any] = {}
        if isinstance(row, dict):
            for k, v in row.items():
                hk = map_header(k)
                if hk:
                    mapped[hk] = v
        else:
            work = list(row)
            if len(work) > len(headers) and str(work[0] or "").strip().isdigit():
                work = work[1:]
            if len(work) > len(headers):
                work = work[: len(headers)]
            for i, cell in enumerate(work):
                if i < len(headers) and headers[i]:
                    mapped[headers[i]] = cell

        region = norm_header(mapped.get("区域") or mapped.get("区域名称") or "")
        if region and region != REGION_NAME:
            continue
        if not any(str(v or "").strip() for v in mapped.values()):
            continue

        progress = parse_progress(mapped.get("完成进度"))
        mapped["完成进度"] = progress if progress is not None else mapped.get("完成进度")
        mapped["考核开始"] = parse_date_value(mapped.get("考核开始"))
        mapped["考核结束"] = parse_date_value(mapped.get("考核结束"))
        mapped["更新日期"] = parse_date_value(mapped.get("更新日期"))
        out.append(mapped)
    return out


def count_noncompliant_cities(rows: list[dict[str, Any]]) -> int:
    """有任一 todo 完成进度 < 1 的合作城市数。"""
    bad: set[str] = set()
    for row in rows:
        p = parse_progress(row.get("完成进度"))
        if p is not None and p < 1:
            city = str(row.get("合作城市") or "").strip()
            if city:
                bad.add(city)
    return len(bad)


def count_incomplete(rows: list[dict[str, Any]]) -> int:
    n = 0
    for row in rows:
        p = parse_progress(row.get("完成进度"))
        if p is not None and p < 1:
            n += 1
    return n


def latest_update_date(rows: list[dict[str, Any]]) -> date | None:
    dates = [d for d in (parse_date_value(r.get("更新日期")) for r in rows) if d]
    return max(dates) if dates else None


def format_progress_cell(value: Any) -> str:
    p = parse_progress(value)
    if p is None:
        return str(value or "").strip()
    pct = p * 100
    if abs(pct - round(pct)) < 1e-6:
        return f"{int(round(pct))}%"
    return f"{pct:.1f}%"


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.4g}".rstrip("0").rstrip(".")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def rows_for_table(rows: list[dict[str, Any]]) -> list[list[str]]:
    table: list[list[str]] = []
    for row in rows:
        cells: list[str] = []
        for h in EXPECTED_HEADERS:
            raw = row.get(h)
            if h == "完成进度":
                cells.append(format_progress_cell(raw))
            else:
                cells.append(format_cell(raw))
        table.append(cells)
    return table
