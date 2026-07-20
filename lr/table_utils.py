"""LR 日报：表头归一化、网页抓取结果解析。"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from config import CITIES, REGION_NAME, normalize_city


def norm_header(name: Any) -> str:
    s = str(name or "").replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# 网页列名 → 模板「数据源(日)」列名
HEADER_ALIASES: dict[str, str] = {
    "区域": "区域",
    "城市": "组织结构",
    "组织结构": "组织结构",
    "日期": "日",
    "日": "日",
    "原价交易额": "原价交易额",
    "商品原价交易额": "商品原价交易额",
    "餐盒费": "餐盒费",
    "合作商补贴金额": "合作商补贴金额",
    "合作商补贴率(页面代补率)": "合作商补贴率 (页面代补率)",
    "合作商补贴率 (页面代补率)": "合作商补贴率 (页面代补率)",
    "页面代补率": "合作商补贴率 (页面代补率)",
    "全量订单": "全量订单",
    "专送订单量": "专送订单量",
    "专送主板订单量": "专送主板订单量",
    "专送PHF订单量": "专送PHF订单量",
    "众包主板": " 众包主板",
    " 众包主板": " 众包主板",
    "众包PHF": " 众包PHF",
    " 众包PHF": " 众包PHF",
    "众包跑腿": "众包跑腿",
    "高校订单": " 高校订单",
    " 高校订单": " 高校订单",
    "活动补贴": "活动补贴",
    "商家服务费": "商家服务费",
    "专送配送费": "专送配送费",
    "后台收入": "后台收入",
    "调账": "调账",
    "套补金额": "套补金额",
}


def map_header(name: Any) -> str | None:
    key = norm_header(name)
    if key in HEADER_ALIASES:
        return HEADER_ALIASES[key]
    # 宽松匹配：去空格后相等
    compact = key.replace(" ", "")
    for src, dst in HEADER_ALIASES.items():
        if src.replace(" ", "") == compact:
            return dst
    return key or None


def parse_cell_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (int, float, datetime, date)):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            return s
    return s


def parse_scrape_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """将浏览器抓取的 {headers, rows} 转为模板行 dict 列表。"""
    headers = [map_header(h) for h in payload.get("headers") or []]
    rows_in = payload.get("rows") or []
    out: list[dict[str, Any]] = []

    for row in rows_in:
        if isinstance(row, dict):
            mapped = {map_header(k) or norm_header(k): parse_cell_value(v) for k, v in row.items()}
        else:
            mapped = {}
            for i, cell in enumerate(row):
                if i < len(headers) and headers[i]:
                    mapped[headers[i]] = parse_cell_value(cell)
        region = norm_header(mapped.get("区域"))
        city = normalize_city(mapped.get("组织结构"))
        day = mapped.get("日")
        if isinstance(day, datetime):
            day = day.date()
        elif isinstance(day, str) and len(day) >= 10:
            day = day[:10]

        if region != REGION_NAME:
            continue
        if city not in CITIES:
            continue
        mapped["区域"] = REGION_NAME
        mapped["组织结构"] = city
        mapped["日"] = day
        out.append(mapped)
    return out


def filter_target_date(rows: list[dict[str, Any]], target: date) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for row in rows:
        day = row.get("日")
        if isinstance(day, datetime):
            day = day.date()
        elif isinstance(day, str):
            day = datetime.strptime(day[:10], "%Y-%m-%d").date()
        if day == target:
            picked.append(row)
    return picked
