"""从初心「新商考核」Metabase 各模块页同步「同分群数值对比」。

数据源：与主看板同一公开看板，按模块 Tab 分别拉取全国城市指标；
分群 / 预警区间取自「模块数据汇总表」；同分群最大 / 中位 / 最小按分群自算。
完全替代 Excel 子表同步。
"""
from __future__ import annotations

import argparse
import json
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "xinshang"
HTMLS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]

MB_HOST = "http://47.112.178.78:3000"
MB_DASH_UUID = "5d509c91-583b-4229-89ee-51721035ae71"
TARGET_CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
CITY_KEYS = [
    ("彭州市", ("彭州市", "彭州")),
    ("仁寿县", ("仁寿县", "仁寿")),
    ("合江县", ("合江县", "合江")),
    ("南溪", ("南溪区", "南溪县", "南溪")),
    ("叙永", ("叙永县", "叙永")),
]

SUMMARY_CARD = {
    "dashcard": 192,
    "card": 214,
    "date_id": "fe957d70",
    "date_type": "date/range",
}

MODULE_CARDS = {
    "waimai": {"dashcard": 198, "card": 217, "date_id": "20b71f6", "date_type": "date/range", "tab": "外卖模块"},
    "retail": {"dashcard": 199, "card": 219, "date_id": "141a2780", "date_type": "date/range", "tab": "零售模块"},
    "tuango": {"dashcard": 197, "card": 215, "date_id": "c717dd65", "date_type": "date/all-options", "tab": "团购模块"},
    "biz": {"dashcard": 177, "card": 202, "date_id": "145eb979", "date_type": "date/range", "tab": "商业增值模块"},
    "lvyue": {"dashcard": 178, "card": 204, "date_id": "3dbda5d5", "date_type": "date/range", "tab": "履约模块"},
    "ux": {"dashcard": 189, "card": 211, "date_id": "c8d3a576", "date_type": "date/range", "tab": "用户体验"},
    "zhili": {"dashcard": 316, "card": 335, "date_id": "44123529", "date_type": "date/all-options", "tab": "综合治理_虚假业绩"},
}

# 现有看板 18 个同分群指标：模块页字段优先，汇总表作分群/预警与兜底
# gap_*: 追平缺口底数。
# gap_mode=month_first：月累计 = 追平率差 × 本城分母；剩余日均 = 月累计 / 剩余天数。
# gap_mode=yoy_catchup（零售 YoY）：
#   月累计 = 本城基期 × (1 + 目标YoY) × 当月天数 − 本城日均 × (模块日 + 2)
#   剩余天数 = 当月天数 − (模块日 + 2)；剩余日均 = 月累计 / 剩余天数
# higher_better=False：追平按「压降」口径，月累计 = (本城−目标) × 分母。
METRIC_SPECS = [
    {
        "id": "外卖模块-市场开发率（订单）",
        "module": "外卖模块",
        "name": "市场开发率（订单）",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "waimai",
        "value_keys": ["市场开发率差值", "市场开发率"],
        "summary_value": "市场开发率（订单）指标值-外卖",
        "cluster_key": "外卖能力分群",
        "warn_keys": ["市场开发率（订单）-外卖"],
        "module_warn": "外卖模块预警",
        "gap_denom_keys": ["行业月累积订单量"],
        "gap_numer_keys": ["订单量"],
        "gap_unit": "单",
        "higher_better": True,
    },
    {
        "id": "外卖模块-市场开发率（实付",
        "module": "外卖模块",
        "name": "市场开发率（实付",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "waimai",
        "value_keys": ["市场开发率_GMV差值", "市场开发率_GMV"],
        "summary_value": "市场开发率（实付）指标值-外卖",
        "cluster_key": "外卖能力分群",
        "warn_keys": ["市场开发率（实付）-外卖"],
        "module_warn": "外卖模块预警",
        "gap_denom_keys": ["行业月累积GMV"],
        "gap_numer_keys": ["实付交易额"],
        "gap_unit": "元",
        "higher_better": True,
    },
    {
        "id": "外卖模块-餐饮商家渗透率",
        "module": "外卖模块",
        "name": "餐饮商家渗透率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "waimai",
        "value_keys": ["餐饮渗透率"],
        "summary_value": "餐饮商家渗透率指标值-外卖",
        "cluster_key": "外卖能力分群",
        "warn_keys": ["餐饮商家渗透率-外卖"],
        "module_warn": "外卖模块预警",
        "gap_denom_keys": ["公海商家数"],
        "gap_numer_keys": ["交易商家数"],
        "gap_unit": "家",
        "higher_better": True,
        "prefer_implied_denom": True,
    },
    {
        "id": "团购模块-市场开发率",
        "module": "团购模块",
        "name": "市场开发率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "tuango",
        "value_keys": ["市场开发率"],
        "summary_value": "市场开发率指标值-团购",
        "cluster_key": "团购能力分群",
        "warn_keys": ["市场开发率-团购"],
        "module_warn": "团购模块预警",
        "gap_denom_keys": ["行业GTV(申诉修正后)"],
        "gap_numer_keys": ["美团实付GTV"],
        "gap_unit": "元",
        "higher_better": True,
    },
    {
        "id": "团购模块-优质商家渗透率",
        "module": "团购模块",
        "name": "优质商家渗透率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "tuango",
        "value_keys": ["优质商家渗透率"],
        "summary_value": "优质商家渗透率指标值-团购",
        "cluster_key": "团购能力分群",
        "warn_keys": ["优质商家渗透率-团购"],
        "module_warn": "团购模块预警",
        "gap_denom_keys": ["整体商家数"],
        "gap_numer_keys": ["4N+1动销商家数"],
        "gap_unit": "家",
        "higher_better": True,
        "prefer_implied_denom": True,
    },
    {
        "id": "履约模块-推单完成率",
        "module": "履约模块",
        "name": "推单完成率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "lvyue",
        "value_keys": ["推单完成率_调度后", "履约_推单完成率（预警值）"],
        "summary_value": "推单完成率指标值-履约",
        "cluster_key": "履约能力分群",
        "warn_keys": ["推单完成率排名-履约"],
        "module_warn": "履约模块预警",
        "gap_denom_keys": ["美配推订单完成率分母_不含散单"],
        "gap_numer_keys": ["美配推订单完成率分子_不含散单"],
        "gap_unit": "单",
        "higher_better": True,
    },
    {
        "id": "履约模块-压力天出勤率",
        "module": "履约模块",
        "name": "压力天出勤率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "lvyue",
        "value_keys": ["压力天出勤率"],
        "summary_value": "压力天出勤率",
        "cluster_key": "履约能力分群",
        "warn_keys": ["压力天出勤率-履约"],
        "module_warn": "履约模块预警",
        "default_warn": "暂不预警",
        "gap_unit": "pp",
        "higher_better": True,
        "gap_rate_only": True,
    },
    {
        "id": "履约模块-超45分钟且超时订单占比",
        "module": "履约模块",
        "name": "超45分钟且超时订单占比",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "lvyue",
        "value_keys": ["超45分钟订单占比", "履约_超45分钟订单占比（预警值）"],
        "summary_value": "超45分钟订单占比指标值-履约",
        "cluster_key": "履约能力分群",
        "warn_keys": ["超45分钟订单占比-履约"],
        "module_warn": "履约模块预警",
        "gap_denom_keys": ["配送完成运单量"],
        "gap_numer_keys": ["超45分钟订单数量"],
        "gap_unit": "单",
        "higher_better": False,
    },
    {
        "id": "零售模块-YoY",
        "module": "零售模块",
        "name": "YoY",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "retail",
        "value_keys": ["非餐YOY"],
        "summary_value": "YoY指标值-零售",
        "cluster_key": "零售能力分群",
        "warn_keys": ["YoY-零售预警"],
        "module_warn": "零售模块预警",
        "gap_denom_keys": ["非餐实付金额_基期"],
        "gap_numer_keys": ["非餐实付金额_日均"],
        "gap_unit": "元",
        "higher_better": True,
        "gap_mode": "yoy_catchup",
    },
    {
        "id": "零售模块-优质仓数达标情况",
        "module": "零售模块",
        "name": "优质仓数达标情况",
        "fields": ["预警区间", "分群", "本期值", "是否达标"],
        "src": "retail",
        "value_keys": ["优质仓达标情况"],
        "summary_value": "优质仓数达标情况",
        "cluster_key": "零售能力分群",
        "warn_keys": [],
        "module_warn": "零售模块预警",
        "default_warn": "暂不预警",
        "no_peer_stats": True,
        "gap_unit": "个",
        "higher_better": True,
        "gap_absolute": True,
    },
    {
        "id": "商业增值-综合货币化率",
        "module": "商业增值",
        "name": "综合货币化率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "biz",
        "value_keys": ["综合货币化率"],
        "summary_value": "综合货币化率指标值-商业增值",
        "cluster_key": "商业增值分群_外卖",
        "cluster_alt": "商业增值分群",
        "warn_keys": ["综合货币化率（外卖货币化率_团购货币化率）-商业增值"],
        "module_warn": "商业增值模块预警",
        "gap_denom_keys": ["实付交易额_GMV", "实付验证GTV"],
        "gap_numer_keys": ["外卖广告现金实收金额", "团购广告现金收入"],
        "gap_unit": "元",
        "higher_better": True,
        "gap_denom_sum": True,
    },
    {
        "id": "商业增值-外卖货币化率",
        "module": "商业增值",
        "name": "外卖货币化率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "biz",
        "value_keys": ["外卖货币化率"],
        "summary_value": "外卖货币化率指标值-商业增值",
        "cluster_key": "商业增值分群_外卖",
        "warn_keys": ["商业增值_外卖货币化率排名"],
        "module_warn": "商业增值模块预警",
        "rank_as_warn": True,
        "gap_denom_keys": ["实付交易额_GMV"],
        "gap_numer_keys": ["外卖广告现金实收金额"],
        "gap_unit": "元",
        "higher_better": True,
    },
    {
        "id": "商业增值-团购货币化率",
        "module": "商业增值",
        "name": "团购货币化率",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "biz",
        "value_keys": ["团购货币化率"],
        "summary_value": "团购货币化率指标值-商业增值",
        "cluster_key": "商业增值分群_团购",
        "warn_keys": ["商业增值_团购货币化率排名"],
        "module_warn": "商业增值模块预警",
        "rank_as_warn": True,
        "gap_denom_keys": ["实付验证GTV"],
        "gap_numer_keys": ["团购广告现金收入"],
        "gap_unit": "元",
        "higher_better": True,
    },
    {
        "id": "用户体验-用户投诉商家问题万服",
        "module": "用户体验",
        "name": "用户投诉商家问题万服",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "ux",
        "value_keys": ["用户商家万服差值"],
        "summary_value": "用户体验_用户投诉商家问题万服差值",
        "cluster_key": "用户体验分群",
        "warn_keys": ["用户体验_用户投诉商家问题万服差值排名"],
        "module_warn": "用户体验模块预警",
        "keep_raw_number": True,
        "gap_unit": "",
        "higher_better": False,
        "gap_absolute": True,
    },
    {
        "id": "用户体验-用户投诉履约问题万服",
        "module": "用户体验",
        "name": "用户投诉履约问题万服",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "ux",
        "value_keys": ["用户履约万服差值"],
        "summary_value": "用户体验_用户投诉履约问题万服差值",
        "cluster_key": "用户体验分群",
        "warn_keys": ["用户体验_用户投诉履约问题万服差值排名"],
        "module_warn": "用户体验模块预警",
        "keep_raw_number": True,
        "gap_unit": "",
        "higher_better": False,
        "gap_absolute": True,
    },
    {
        "id": "综合治理-虚假业绩_外卖",
        "module": "综合治理",
        "name": "虚假业绩_外卖",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "zhili",
        "value_keys": ["月外卖虚假占比"],
        "summary_value": "月外卖虚假业绩占比",
        "cluster_key": "综合治理分群",
        "warn_keys": ["综合治理能力预警"],
        "default_warn": "暂无预警",
        "gap_denom_keys": ["月实付GTV"],
        "gap_numer_keys": ["月外卖虚假交易额"],
        "gap_unit": "元",
        "higher_better": False,
    },
    {
        "id": "综合治理-虚假业绩_团购",
        "module": "综合治理",
        "name": "虚假业绩_团购",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "zhili",
        "value_keys": ["团购异常实付GTV占比"],
        "summary_value": "月团购虚假业绩占比",
        "cluster_key": "综合治理分群",
        "warn_keys": ["综合治理能力预警"],
        "default_warn": "暂无预警",
        "gap_denom_keys": ["实付验证GTV"],
        "gap_numer_keys": ["团购异常实付GTV"],
        "gap_unit": "元",
        "higher_better": False,
    },
    {
        "id": "综合治理-虚假业绩_异常骑手数",
        "module": "综合治理",
        "name": "虚假业绩_异常骑手数",
        "fields": ["预警区间", "分群", "本期值", "同分群最大值", "同分群中位值", "同分群最小值"],
        "src": "zhili",
        "value_keys": ["异常骑手率"],
        "summary_value": "月异常骑手率",
        "cluster_key": "综合治理分群",
        "warn_keys": ["综合治理能力预警"],
        "default_warn": "暂无预警",
        "gap_denom_keys": ["有完成单骑手数"],
        "gap_numer_keys": ["异常骑手人次"],
        "gap_unit": "人",
        "higher_better": False,
    },
]


def http_json(url: str, timeout: int = 180):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def blank(v) -> bool:
    return v is None or v == "" or v == "None" or (isinstance(v, float) and v != v)


def cell_str(v) -> str:
    if blank(v):
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d") if v.hour == 0 and v.minute == 0 and v.second == 0 else v.isoformat()
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none", "nat"} else s


def canon_city(v) -> str | None:
    s = cell_str(v).replace(" ", "").replace("\n", "").replace("\r", "")
    if not s:
        return None
    hits = []
    for canon, keys in CITY_KEYS:
        for k in keys:
            if k in s:
                hits.append((len(k), canon))
                break
    if not hits:
        return s
    hits.sort(reverse=True)
    return hits[0][1]


def latest_param_date(param_id: str) -> str:
    url = f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}/params/{param_id}/values"
    vals = [str(v[0])[:10] for v in (http_json(url).get("values") or []) if v]
    days = sorted({d for d in vals if len(d) >= 10 and d[4] == "-" and d[0].isdigit()})
    if not days:
        raise RuntimeError(f"参数 {param_id} 没有可用日期")
    return days[-1]


def date_value(day: str, kind: str):
    return f"{day}~{day}" if kind == "date/range" else day


def query_card(spec: dict, day: str) -> tuple[list[str], list[list]]:
    parameters = [
        {"type": spec["date_type"], "value": date_value(day, spec["date_type"]), "id": spec["date_id"]},
    ]
    q = urllib.parse.urlencode({"parameters": json.dumps(parameters, ensure_ascii=False)})
    url = (
        f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}"
        f"/dashcard/{spec['dashcard']}/card/{spec['card']}?{q}"
    )
    payload = http_json(url)
    data = payload.get("data") or {}
    cols = [c.get("display_name") or c.get("name") for c in (data.get("cols") or [])]
    rows = data.get("rows") or []
    return cols, rows


def rows_to_city_map(cols, rows) -> dict[str, dict]:
    out = {}
    for row in rows:
        d = dict(zip(cols, row))
        city = canon_city(d.get("城市"))
        if not city:
            continue
        out[city] = d
    return out


def parse_metric_value(v, keep_raw_number: bool = False):
    """百分数转小数（与旧 Excel 口径一致）；不考核等保留原文；万服差值保留原数。"""
    if blank(v):
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v != v:
            return None
        num = float(v)
        if keep_raw_number:
            return round(num, 6)
        # 模块里偶发已是 0~1 比例
        if abs(num) <= 2:
            return round(num, 6)
        # 异常骑手率等可能是 0.015% 已带百分号字符串；纯数字大值按原样
        return round(num, 6)
    s = cell_str(v)
    if not s:
        return None
    if s in {"不考核", "数据准备中", "不适用", "—", "-"}:
        return s
    is_pct = s.endswith("%")
    body = s[:-1].replace(",", "").strip() if is_pct else s.replace(",", "").strip()
    try:
        num = float(body)
    except ValueError:
        return s
    if keep_raw_number and not is_pct:
        return round(num, 6)
    if is_pct:
        return round(num / 100.0, 6)
    return round(num, 6)


def pick_value(row: dict | None, keys: list[str], summary: dict | None, summary_key: str, keep_raw: bool):
    """本期值：优先汇总表考核指标值（与主看板一致）；模块页仅作补充；都没有返回 None。"""
    if summary and summary_key and not blank(summary.get(summary_key)):
        return parse_metric_value(summary.get(summary_key), keep_raw_number=keep_raw)
    if row:
        for k in keys:
            if k in row and not blank(row.get(k)):
                return parse_metric_value(row.get(k), keep_raw_number=keep_raw)
    return None


MISSING_VALUE = "暂无数据"


def pick_warn(spec: dict, summary: dict | None, module_row: dict | None):
    if summary:
        for k in spec.get("warn_keys") or []:
            v = cell_str(summary.get(k))
            if not v:
                continue
            if spec.get("rank_as_warn"):
                # 排名为 0 时按官方口径视为不预警
                try:
                    if abs(float(v.replace("%", ""))) < 1e-12:
                        return "不预警"
                except ValueError:
                    pass
                if v in {"0", "0.0"}:
                    return "不预警"
            return v
    if module_row:
        mw = cell_str(module_row.get(spec.get("module_warn") or ""))
        if mw:
            return mw
    return spec.get("default_warn") or "—"


def pick_cluster(spec: dict, summary: dict | None) -> str:
    if not summary:
        return "无分群"
    for k in (spec.get("cluster_key"), spec.get("cluster_alt")):
        if not k:
            continue
        v = cell_str(summary.get(k))
        if not v:
            continue
        if v in {"无", "无分群", "—", "-"}:
            return "无分群"
        return v
    return "无分群"


def peer_stats(values: list[float]) -> tuple[float | None, float | None, float | None]:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None, None, None
    return round(max(nums), 6), round(statistics.median(nums), 6), round(min(nums), 6)


def extract_data_json(html: str) -> tuple[int, int, dict]:
    marker = "const DATA = "
    start = html.index(marker) + len(marker)
    while html[start].isspace():
        start += 1
    depth = 0
    in_str = False
    esc = False
    end = None
    for j, ch in enumerate(html[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        raise RuntimeError("无法定位 DATA JSON 结束位置")
    return start, end, json.loads(html[start:end])


def parse_count(v):
    if blank(v):
        return None
    s = str(v).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def sum_counts(row: dict | None, keys: list[str]) -> float | None:
    if not row:
        return None
    total = 0.0
    hit = False
    for k in keys:
        n = parse_count(row.get(k))
        if n is None:
            continue
        total += n
        hit = True
    return total if hit else None


def pick_gap_denom(spec: dict, mrow: dict | None, rate) -> float | None:
    """追平分母：优先模块绝对量；考核率与分子不一致时可用分子/率反推。"""
    if spec.get("gap_rate_only") or spec.get("gap_absolute"):
        return None
    denom_keys = list(spec.get("gap_denom_keys") or [])
    numer_keys = list(spec.get("gap_numer_keys") or [])
    prefer_implied = bool(spec.get("prefer_implied_denom"))

    def implied():
        if not isinstance(rate, (int, float)) or abs(float(rate)) < 1e-12:
            return None
        numer = sum_counts(mrow, numer_keys) if numer_keys else None
        if numer is None:
            return None
        return abs(float(numer) / float(rate))

    if prefer_implied:
        d = implied()
        if d is not None and d > 0:
            return d

    if spec.get("gap_denom_sum"):
        d = sum_counts(mrow, denom_keys)
        if d is not None and d > 0:
            return d
    else:
        for k in denom_keys:
            d = parse_count((mrow or {}).get(k))
            if d is not None and d > 0:
                return d

    d = implied()
    if d is not None and d > 0:
        return d
    return None


def module_row_date(mrow: dict | None) -> str:
    if not mrow:
        return ""
    for k in ("最新数据日期", "数据日期", "日期"):
        s = cell_str(mrow.get(k))
        if len(s) >= 10 and s[4] == "-":
            return s[:10]
    return ""


def prev_param_date(param_id: str, day: str) -> str | None:
    url = f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}/params/{param_id}/values"
    vals = [str(v[0])[:10] for v in (http_json(url).get("values") or []) if v]
    days = sorted({d for d in vals if len(d) >= 10 and d[4] == "-" and d[0].isdigit()})
    older = [d for d in days if d < day]
    return older[-1] if older else None


def remaining_days(module_day: str) -> int | None:
    """剩余日均天数 = 当月天数 − (模块最左日期日号 + 2)。例：8/24 → 31−26=5。"""
    if not module_day or len(module_day) < 10:
        return None
    try:
        y, m, d = int(module_day[:4]), int(module_day[5:7]), int(module_day[8:10])
    except ValueError:
        return None
    if m == 12:
        next_month = datetime(y + 1, 1, 1)
    else:
        next_month = datetime(y, m + 1, 1)
    month_days = (next_month - datetime(y, m, 1)).days
    return max(0, month_days - (d + 2))


def fetch_all(day: str | None = None):
    CACHE.mkdir(parents=True, exist_ok=True)
    period = day or latest_param_date(SUMMARY_CARD["date_id"])
    prev = prev_param_date(SUMMARY_CARD["date_id"], period)
    dump = {
        "periodDate": period,
        "prevDate": prev,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "modules": {},
    }

    scols, srows = query_card(SUMMARY_CARD, period)
    summary = rows_to_city_map(scols, srows)
    dump["summary"] = {"n": len(srows), "cities": len(summary)}

    summary_prev = {}
    if prev:
        pcols, prows = query_card(SUMMARY_CARD, prev)
        summary_prev = rows_to_city_map(pcols, prows)
        dump["summary_prev"] = {"n": len(prows), "cities": len(summary_prev), "date": prev}

    modules = {}
    for name, spec in MODULE_CARDS.items():
        use_day = period
        cols, rows = query_card(spec, use_day)
        if not rows:
            alt = latest_param_date(spec["date_id"])
            if alt != use_day:
                use_day = alt
                cols, rows = query_card(spec, use_day)
        modules[name] = rows_to_city_map(cols, rows)
        dump["modules"][name] = {
            "tab": spec["tab"],
            "day": use_day,
            "n": len(rows),
            "cities": len(modules[name]),
            "remainingDays": remaining_days(use_day),
        }

    (CACHE / "peer_compare_metabase.json").write_text(
        json.dumps({"meta": dump}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return period, prev, summary, summary_prev, modules, dump


def build_city_universe(summary: dict, summary_prev: dict, modules: dict) -> set[str]:
    """城市名单：本期汇总表 ∪ 上期汇总表（约 117 城）。汇总表单日缩水时用上期补全，不把各模块页独有城市并入名单。"""
    cities: set[str] = set(summary.keys())
    if summary_prev:
        cities |= set(summary_prev.keys())
    return cities


def build_payload(period: str, prev: str | None, summary: dict, summary_prev: dict, modules: dict, dump: dict) -> dict:
    universe = build_city_universe(summary, summary_prev, modules)
    if not universe:
        raise RuntimeError("模块数据汇总表没有城市数据")
    if summary and len(summary) < len(universe):
        dump.setdefault("cityUniverseNote", (
            f"本期汇总表仅 {len(summary)} 城，已并入上期汇总表共 {len(universe)} 城"
        ))

    def city_sort_key(c: str):
        srow = summary.get(c) or summary_prev.get(c) or {}
        return (0 if c in TARGET_CITIES else 1, cell_str(srow.get("区域")), c)

    ordered = sorted(universe, key=city_sort_key)

    # 先填每城每指标的本期值/上期值/分群/预警/缺口分母
    raw_by_metric: dict[str, dict[str, dict]] = {m["id"]: {} for m in METRIC_SPECS}
    for city in ordered:
        srow = summary.get(city) or {}
        sprow = summary_prev.get(city) or {}
        meta_row = srow or sprow
        for spec in METRIC_SPECS:
            mrow = (modules.get(spec["src"]) or {}).get(city)
            val = pick_value(
                mrow,
                spec["value_keys"],
                srow,
                spec.get("summary_value") or "",
                keep_raw=bool(spec.get("keep_raw_number")),
            )
            prev_val = pick_value(
                None,
                [],
                sprow,
                spec.get("summary_value") or "",
                keep_raw=bool(spec.get("keep_raw_number")),
            )
            if prev_val is None and mrow:
                # 上期优先汇总表；没有则不硬凑模块上期（避免与考核口径不一致）
                prev_val = None
            if val is None:
                val = MISSING_VALUE
            cluster = pick_cluster(spec, meta_row)
            warn = pick_warn(spec, meta_row, mrow)
            region = cell_str(
                srow.get("区域") or sprow.get("区域") or (mrow or {}).get("区域") or (mrow or {}).get("配送区域")
            )
            level = cell_str(
                srow.get("城市等级") or sprow.get("城市等级") or (mrow or {}).get("城市等级") or (mrow or {}).get("等级")
            )
            gap_denom = pick_gap_denom(spec, mrow, val if isinstance(val, (int, float)) else None)
            gap_daily = sum_counts(mrow, list(spec.get("gap_numer_keys") or [])[:1]) if spec.get("gap_numer_keys") else None
            # 零售 YoY：显式保留基期 + 日均，供 yoy_catchup 公式使用
            if spec.get("gap_mode") == "yoy_catchup":
                gap_denom = parse_count((mrow or {}).get("非餐实付金额_基期"))
                gap_daily = parse_count((mrow or {}).get("非餐实付金额_日均"))
            mod_day = module_row_date(mrow) or ((dump.get("modules") or {}).get(spec["src"]) or {}).get("day") or period
            raw_by_metric[spec["id"]][city] = {
                "本期值": val,
                "上期值": prev_val if prev_val is not None else MISSING_VALUE,
                "分群": cluster,
                "预警区间": warn,
                "区域": region,
                "城市等级": level,
                "gapDenom": gap_denom,
                "gapDaily": gap_daily,
                "gapUnit": spec.get("gap_unit") or "",
                "higherBetter": bool(spec.get("higher_better", True)),
                "gapMode": spec.get("gap_mode") or "month_first",
                "gapAbsolute": bool(spec.get("gap_absolute")),
                "gapRateOnly": bool(spec.get("gap_rate_only")),
                "moduleDate": mod_day,
            }

    # 按分群计算最大/中位/最小
    stats_by_metric: dict[str, dict[str, tuple]] = {}
    for spec in METRIC_SPECS:
        mid = spec["id"]
        if spec.get("no_peer_stats"):
            stats_by_metric[mid] = {}
            continue
        buckets: dict[str, list[float]] = {}
        for city, block in raw_by_metric[mid].items():
            cl = block.get("分群") or "无分群"
            v = block.get("本期值")
            if isinstance(v, (int, float)):
                buckets.setdefault(cl, []).append(float(v))
        stats_by_metric[mid] = {cl: peer_stats(vals) for cl, vals in buckets.items()}

    records = []
    for city in ordered:
        sample = next((raw_by_metric[m["id"]][city] for m in METRIC_SPECS if city in raw_by_metric[m["id"]]), {})
        values = {}
        for spec in METRIC_SPECS:
            mid = spec["id"]
            block = raw_by_metric[mid].get(city)
            if not block:
                continue
            cl = block.get("分群") or "无分群"
            item = {
                "预警区间": block.get("预警区间"),
                "本期值": block.get("本期值"),
                "上期值": block.get("上期值"),
                "gapDenom": block.get("gapDenom"),
                "gapDaily": block.get("gapDaily"),
                "gapUnit": block.get("gapUnit"),
                "higherBetter": block.get("higherBetter"),
                "gapMode": block.get("gapMode"),
                "gapAbsolute": block.get("gapAbsolute"),
                "gapRateOnly": block.get("gapRateOnly"),
                "moduleDate": block.get("moduleDate"),
            }
            if "分群" in spec["fields"]:
                item["分群"] = cl
            if not spec.get("no_peer_stats"):
                mx, md, mn = stats_by_metric[mid].get(cl, (None, None, None))
                item["同分群最大值"] = mx
                item["同分群中位值"] = md
                item["同分群最小值"] = mn
            if "是否达标" in spec["fields"]:
                item["是否达标"] = None
            values[mid] = item
        records.append(
            {
                "城市": city,
                "区域": sample.get("区域") or "",
                "城市等级": sample.get("城市等级") or "",
                "mine": city in TARGET_CITIES,
                "values": values,
            }
        )

    records.sort(key=lambda x: (0 if x["mine"] else 1, x.get("区域") or "", x["城市"]))
    mine_cities = [c for c in TARGET_CITIES if any(r["城市"] == c for r in records)]
    all_cities = []
    seen = set()
    for r in records:
        if r["城市"] not in seen:
            seen.add(r["城市"])
            all_cities.append(r["城市"])

    metrics_meta = []
    for m in METRIC_SPECS:
        metrics_meta.append(
            {
                "id": m["id"],
                "module": m["module"],
                "name": m["name"],
                "fields": list(m["fields"]),
                "src": m.get("src"),
                "gapUnit": m.get("gap_unit") or "",
                "higherBetter": bool(m.get("higher_better", True)),
                "gapMode": m.get("gap_mode") or "month_first",
                "gapAbsolute": bool(m.get("gap_absolute")),
                "gapRateOnly": bool(m.get("gap_rate_only")),
            }
        )

    # 扁平表兜底（兼容旧渲染）
    flat_headers = ["城市", "区域", "城市等级"]
    for m in metrics_meta:
        for fld in ("本期值", "上期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间", "是否达标"):
            if fld == "上期值" or fld in m["fields"]:
                flat_headers.append(f"{m['name']}-{fld}")
    flat_rows = []
    for rec in records:
        row = {"城市": rec["城市"], "区域": rec["区域"], "城市等级": rec["城市等级"]}
        for m in metrics_meta:
            block = rec["values"].get(m["id"]) or {}
            for fld in ("本期值", "上期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间", "是否达标"):
                if fld == "上期值" or fld in m["fields"]:
                    row[f"{m['name']}-{fld}"] = block.get(fld)
        flat_rows.append(row)

    module_dates = {k: (v or {}).get("day") for k, v in (dump.get("modules") or {}).items()}
    remain_by_src = {k: (v or {}).get("remainingDays") for k, v in (dump.get("modules") or {}).items()}

    return {
        "sheet": "新商考核·各模块Tab",
        "layout": "official",
        "periodDate": period,
        "prevDate": prev,
        "cityField": "城市",
        "metrics": metrics_meta,
        "mineCities": mine_cities,
        "cities": mine_cities,
        "allCities": all_cities,
        "records": records,
        "headers": flat_headers,
        "rows": flat_rows,
        "meta": {
            "layout": "official",
            "source": "metabase",
            "cities": mine_cities,
            "allCityCount": len(all_cities),
            "summaryCityCount": len(summary),
            "universeCityCount": len(universe),
            "periodDate": period,
            "prevDate": prev,
            "modules": dump.get("modules"),
            "moduleDates": module_dates,
            "remainingDaysBySrc": remain_by_src,
            "cityUniverseNote": dump.get("cityUniverseNote"),
        },
        "note": (
            "数据来自初心「新商考核」：城市名单=本期汇总表∪上期汇总表（约 117 城；汇总表单日仅 50 行时用上期补全）；"
            "本期值优先用汇总表考核指标值（与主看板一致）；上期值取汇总表上一考核日；"
            "追平缺口用各模块绝对量底数测算；剩余天数=当月天数−(模块日期+2)。"
            "非五城城市/区域展示为「友商」。"
        ),
        "sourceFile": f"metabase:{MB_DASH_UUID}",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="考核日期 YYYY-MM-DD（默认模块数据汇总表最新一日）")
    args = ap.parse_args()

    period, prev, summary, summary_prev, modules, dump = fetch_all(args.date)
    payload = build_payload(period, prev, summary, summary_prev, modules, dump)
    if not payload["records"]:
        raise RuntimeError("同分群对比未拉到任何城市数据")

    html = HTMLS[0].read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)
    data["peerCompare"] = payload
    # 文案：去掉 Excel 表述
    new_html = html[:start] + json.dumps(data, ensure_ascii=False, indent=2) + html[end:]
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出 Excel 里同一分群的全部城市，不只比五城。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市。非五城城市/区域显示为「友商」。对比目标城市差值=目标本期值−本城本期值；追平缺口按各模块绝对量测算，剩余天数=当月天数−(模块日期+2)。",
    )
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市，不只比五城。数据来自各模块页。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市。非五城城市/区域显示为「友商」。对比目标城市差值=目标本期值−本城本期值；追平缺口按各模块绝对量测算，剩余天数=当月天数−(模块日期+2)。",
    )
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市（城市名单以模块数据汇总表为准）。模块缺数回汇总表，再没有显示「暂无数据」。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市。非五城城市/区域显示为「友商」。对比目标城市差值=目标本期值−本城本期值；追平缺口按各模块绝对量测算，剩余天数=当月天数−(模块日期+2)。",
    )
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市（城市名单以模块数据汇总表为准）。本期值优先用汇总表考核指标值；模块缺对应考核字段时再回模块页，再没有显示「暂无数据」。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市。非五城城市/区域显示为「友商」。对比目标城市差值=目标本期值−本城本期值；追平缺口按各模块绝对量测算，剩余天数=当月天数−(模块日期+2)。",
    )
    new_html = new_html.replace(
        "暂无「同分群数值对比」数据。请先运行独立同步脚本导入 Excel 子表。",
        "暂无「同分群数值对比」数据。请先运行 scripts/sync_peer_compare_from_chuxin.py 从新商考核各模块同步。",
    )
    for p in HTMLS:
        p.write_text(new_html, encoding="utf-8")
        print("wrote", p)

    # 抽查五城分群人数
    sample = {}
    mid = "外卖模块-餐饮商家渗透率"
    for city in TARGET_CITIES:
        rec = next((r for r in payload["records"] if r["城市"] == city), None)
        if not rec:
            continue
        cl = str(((rec.get("values") or {}).get(mid) or {}).get("分群") or "")
        n = sum(
            1
            for r in payload["records"]
            if str(((r.get("values") or {}).get(mid) or {}).get("分群") or "") == cl
        )
        block = (rec.get("values") or {}).get(mid) or {}
        sample[city] = {
            "cluster": cl,
            "peers": n,
            "gapDenom": block.get("gapDenom"),
            "prev": block.get("上期值"),
            "moduleDate": block.get("moduleDate"),
        }

    print(
        json.dumps(
            {
                "ok": True,
                "periodDate": period,
                "prevDate": prev,
                "cities": len(payload["records"]),
                "summaryCities": (payload.get("meta") or {}).get("summaryCityCount"),
                "universeCities": (payload.get("meta") or {}).get("universeCityCount"),
                "cityUniverseNote": (payload.get("meta") or {}).get("cityUniverseNote"),
                "mineCities": payload["mineCities"],
                "metrics": len(payload["metrics"]),
                "modules": dump.get("modules"),
                "samplePeers": sample,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
