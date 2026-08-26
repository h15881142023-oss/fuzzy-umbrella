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
    """本期值：模块页优先，缺则回汇总表考核指标值；都没有返回 None（上层写成「暂无数据」）。"""
    if row:
        for k in keys:
            if k in row and not blank(row.get(k)):
                return parse_metric_value(row.get(k), keep_raw_number=keep_raw)
    if summary and summary_key and not blank(summary.get(summary_key)):
        return parse_metric_value(summary.get(summary_key), keep_raw_number=keep_raw)
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


def fetch_all(day: str | None = None):
    CACHE.mkdir(parents=True, exist_ok=True)
    period = day or latest_param_date(SUMMARY_CARD["date_id"])
    dump = {"periodDate": period, "fetchedAt": datetime.now(timezone.utc).isoformat(), "modules": {}}

    scols, srows = query_card(SUMMARY_CARD, period)
    summary = rows_to_city_map(scols, srows)
    dump["summary"] = {"n": len(srows), "cities": len(summary)}

    modules = {}
    for name, spec in MODULE_CARDS.items():
        use_day = period
        cols, rows = query_card(spec, use_day)
        if not rows:
            # 个别模块当日无数据时回退该模块最新日
            alt = latest_param_date(spec["date_id"])
            if alt != use_day:
                use_day = alt
                cols, rows = query_card(spec, use_day)
        modules[name] = rows_to_city_map(cols, rows)
        dump["modules"][name] = {"tab": spec["tab"], "day": use_day, "n": len(rows), "cities": len(modules[name])}

    (CACHE / "peer_compare_metabase.json").write_text(
        json.dumps({"meta": dump}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return period, summary, modules, dump


def build_payload(period: str, summary: dict, modules: dict, dump: dict) -> dict:
    # 城市范围：以模块数据汇总表为准（约 117 城）
    if not summary:
        raise RuntimeError("模块数据汇总表没有城市数据")
    ordered = sorted(summary.keys(), key=lambda c: (0 if c in TARGET_CITIES else 1, cell_str((summary.get(c) or {}).get("区域")), c))

    # 先填每城每指标的本期值/分群/预警
    raw_by_metric: dict[str, dict[str, dict]] = {m["id"]: {} for m in METRIC_SPECS}
    for city in ordered:
        srow = summary.get(city) or {}
        for spec in METRIC_SPECS:
            mrow = (modules.get(spec["src"]) or {}).get(city)
            val = pick_value(
                mrow,
                spec["value_keys"],
                srow,
                spec.get("summary_value") or "",
                keep_raw=bool(spec.get("keep_raw_number")),
            )
            if val is None:
                val = MISSING_VALUE
            cluster = pick_cluster(spec, srow)
            warn = pick_warn(spec, srow, mrow)
            region = cell_str(srow.get("区域") or (mrow or {}).get("区域") or (mrow or {}).get("配送区域"))
            level = cell_str(srow.get("城市等级") or (mrow or {}).get("城市等级") or (mrow or {}).get("等级"))
            raw_by_metric[spec["id"]][city] = {
                "本期值": val,
                "分群": cluster,
                "预警区间": warn,
                "区域": region,
                "城市等级": level,
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

    metrics_meta = [
        {"id": m["id"], "module": m["module"], "name": m["name"], "fields": list(m["fields"])} for m in METRIC_SPECS
    ]

    # 扁平表兜底（兼容旧渲染）
    flat_headers = ["城市", "区域", "城市等级"]
    for m in metrics_meta:
        for fld in ("本期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间", "是否达标"):
            if fld in m["fields"]:
                flat_headers.append(f"{m['name']}-{fld}")
    flat_rows = []
    for rec in records:
        row = {"城市": rec["城市"], "区域": rec["区域"], "城市等级": rec["城市等级"]}
        for m in metrics_meta:
            block = rec["values"].get(m["id"]) or {}
            for fld in ("本期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间", "是否达标"):
                if fld in m["fields"]:
                    row[f"{m['name']}-{fld}"] = block.get(fld)
        flat_rows.append(row)

    return {
        "sheet": "新商考核·各模块Tab",
        "layout": "official",
        "periodDate": period,
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
            "periodDate": period,
            "modules": dump.get("modules"),
        },
        "note": (
            "数据来自初心「新商考核」：城市名单以模块数据汇总表为准；"
            "各指标优先取对应模块页，缺失回汇总表，再没有为「暂无数据」。"
            "同分群最大/中位/最小按分群自算。本城仅限川藏一区五城。"
        ),
        "sourceFile": f"metabase:{MB_DASH_UUID}",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="考核日期 YYYY-MM-DD（默认模块数据汇总表最新一日）")
    args = ap.parse_args()

    period, summary, modules, dump = fetch_all(args.date)
    payload = build_payload(period, summary, modules, dump)
    if not payload["records"]:
        raise RuntimeError("同分群对比未拉到任何城市数据")

    html = HTMLS[0].read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)
    data["peerCompare"] = payload
    # 文案：去掉 Excel 表述
    new_html = html[:start] + json.dumps(data, ensure_ascii=False, indent=2) + html[end:]
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出 Excel 里同一分群的全部城市，不只比五城。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市（城市名单以模块数据汇总表为准）。模块缺数回汇总表，再没有显示「暂无数据」。",
    )
    new_html = new_html.replace(
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市，不只比五城。数据来自各模块页。",
        "本城只选川藏一区五城；选定指标后，按该城该指标的分群列出新商考核同一分群的全部城市（城市名单以模块数据汇总表为准）。模块缺数回汇总表，再没有显示「暂无数据」。",
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
        sample[city] = {"cluster": cl, "peers": n}

    print(
        json.dumps(
            {
                "ok": True,
                "periodDate": period,
                "cities": len(payload["records"]),
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
