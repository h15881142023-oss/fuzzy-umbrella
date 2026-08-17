"""从初心「新商考核」Metabase 看板拉取川藏一区数据，写回详表看板 DATA。

正确数据源：数据平台 → 业务看板 → 新商评 → 新商考核 → 模块数据汇总表
（NocoBase 页面 iframe 指向 Metabase 公开看板，不是测评集合 / html_pages 观测舱）
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

NOCO_BASE = "http://www.chuxin.city"
ADMIN_PAGE = "http://www.chuxin.city/v/admin/b7v8t424ohb"
MB_HOST = "http://47.112.178.78:3000"
MB_DASH_UUID = "5d509c91-583b-4229-89ee-51721035ae71"
COLLECTION = "t_t6e991yzf4c"
REGION = "川藏一区"
CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "xinshang"
HTMLS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]

# 模块数据汇总表 / 城市能力看板 / 外卖模块 / 团购模块
CARDS = {
    "summary": {"dashcard": 192, "card": 214, "date_id": "fe957d70", "date_type": "date/range", "region_id": "9b4dac3b"},
    "cityboard": {"dashcard": 168, "card": 191, "date_id": "54dcbdb2", "date_type": "date/range", "region_id": "a60b4ae9"},
    "waimai": {"dashcard": 198, "card": 217, "date_id": "20b71f6", "date_type": "date/range", "region_id": "4da2372d"},
    "tuango": {"dashcard": 197, "card": 215, "date_id": "c717dd65", "date_type": "date/all-options", "region_id": "c6f05ae6"},
}

BAND_RANK = {
    "(90%-100%]": 6,
    "(70%-90%]": 5,
    "(50%-70%]": 4,
    "(30%-50%]": 3,
    "(10%-30%]": 2,
    "[0%-10%]": 1,
}
NA_BANDS = {"—", "不预警", "暂不预警", "无预警", "不考核", "数据准备中", "不适用", "", None}


def http_json(url: str, timeout: int = 180):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def nocobase(path, token=None, method="GET", data=None, params=None):
    if params:
        path += ("&" if "?" in path else "?") + urllib.parse.urlencode(params, doseq=True)
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(NOCO_BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def login():
    data = nocobase("/api/auth:signIn", method="POST", data={"account": "qiaoxianhai", "password": "123"})
    token = (data.get("data") or {}).get("token")
    if not token:
        raise RuntimeError(f"login failed: {data}")
    return token


def fetch_tests(token):
    items = []
    page = 1
    while True:
        data = nocobase(
            f"/api/{COLLECTION}:list",
            token,
            params={
                "page": page,
                "pageSize": 200,
                "filter": json.dumps({"qy": REGION}, ensure_ascii=False),
                "sort[]": "-updatedAt",
            },
        )
        batch = data.get("data") or []
        items.extend(batch)
        total_page = int((data.get("meta") or {}).get("totalPage") or 1)
        if page >= total_page:
            break
        page += 1
    return items


def summarize_tests(rows):
    by_city = defaultdict(list)
    for r in rows:
        by_city[r.get("cs") or "未知"].append(r)
    city_stats = []
    for city in CITIES + sorted(c for c in by_city if c not in CITIES):
        items = by_city.get(city, [])
        latest = {}
        for x in sorted(items, key=lambda z: z.get("updatedAt") or "", reverse=True):
            name = (x.get("xm") or "").strip() or f"id-{x.get('id')}"
            if name not in latest:
                latest[name] = x
        scores = [float(v["fs"]) for v in latest.values() if v.get("fs") is not None]
        low = [v for v in latest.values() if v.get("fs") is not None and float(v["fs"]) < 90]
        city_stats.append(
            {
                "city": city,
                "records": len(items),
                "people": len(latest),
                "avg": round(sum(scores) / len(scores), 2) if scores else None,
                "min": min(scores) if scores else None,
                "max": max(scores) if scores else None,
                "below90": len(low),
                "latestAt": items[0].get("updatedAt") if items else None,
            }
        )
    people = [
        {
            "city": r.get("cs"),
            "name": r.get("xm"),
            "score": r.get("fs"),
            "note": r.get("bz"),
            "updatedAt": r.get("updatedAt"),
        }
        for r in rows
    ]
    return {
        "cityStats": city_stats,
        "people": people,
        "totalRecords": len(rows),
        "totalPeople": sum(s["people"] for s in city_stats if s["city"] in CITIES),
    }


def latest_summary_date() -> str:
    url = f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}/params/fe957d70/values"
    vals = [v[0] for v in (http_json(url).get("values") or [])]
    if not vals:
        raise RuntimeError("模块数据汇总表没有可用日期")
    return max(vals)


def date_value(iso: str, kind: str):
    day = iso[:10]
    if kind == "date/range":
        return f"{day}~{day}"
    return day


def query_card(spec: dict, iso_date: str, region: str = REGION) -> tuple[list[str], list[list]]:
    parameters = [
        {"type": spec["date_type"], "value": date_value(iso_date, spec["date_type"]), "id": spec["date_id"]},
        {"type": "string/=", "value": [region], "id": spec["region_id"]},
    ]
    q = urllib.parse.urlencode({"parameters": json.dumps(parameters, ensure_ascii=False)})
    url = f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}/dashcard/{spec['dashcard']}/card/{spec['card']}?{q}"
    payload = http_json(url)
    data = payload.get("data") or {}
    cols = [c.get("display_name") or c.get("name") for c in (data.get("cols") or [])]
    rows = data.get("rows") or []
    return cols, rows


def rows_to_city_map(cols, rows, city_key="城市"):
    out = {}
    for row in rows:
        d = dict(zip(cols, row))
        name = d.get(city_key)
        if name:
            out[name] = d
    return out


def blank(v) -> bool:
    return v is None or v == "" or v == "None"


def show(v, fallback="—"):
    if blank(v):
        return fallback
    return str(v).strip()


def is_na_band(v) -> bool:
    return show(v) in NA_BANDS or v in NA_BANDS


def band_delta(old, new):
    a, b = show(old), show(new)
    if is_na_band(a) or is_na_band(b):
        return None
    if a == b:
        return "持平"
    ra, rb = BAND_RANK.get(a), BAND_RANK.get(b)
    if ra is None or rb is None:
        return None
    if rb > ra:
        return "上升"
    if rb < ra:
        return "下降"
    return "持平"


def fmt_pp(v):
    if blank(v):
        return "—"
    s = str(v).strip()
    try:
        if s.endswith("%"):
            num = float(s[:-1])
        else:
            num = float(s)
    except ValueError:
        return s
    if abs(num) < 1e-9:
        return "0"
    sign = "+" if num > 0 else ""
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    return f"{sign}{text}pp"


def fmt_num_delta(v, digits=4):
    if blank(v):
        return "—"
    try:
        num = float(str(v).replace("%", "").strip())
    except ValueError:
        return str(v)
    if abs(num) < 1e-12:
        return "0"
    sign = "+" if num > 0 else ""
    text = f"{num:.{digits}f}".rstrip("0").rstrip(".")
    return f"{sign}{text}"


def metric(value, band=None, value_delta=None, warn_delta=None):
    rec = {"value": show(value)}
    if band is not None and not blank(band):
        rec["band"] = show(band)
    if value_delta not in (None, "—"):
        rec["valueDelta"] = value_delta
    if warn_delta:
        rec["delta"] = warn_delta
    return rec


def pick_latest_board(cols, rows):
    by = defaultdict(list)
    for row in rows:
        d = dict(zip(cols, row))
        if d.get("区域") != REGION:
            continue
        by[d.get("城市")].append(d)
    out = {}
    for city, items in by.items():
        items.sort(key=lambda x: str(x.get("本期日期") or ""), reverse=True)
        if items:
            out[city] = items[0]
    return out


def apply_city(dst: dict, summary: dict, prev: dict | None, board: dict | None, waimai: dict | None, tuango: dict | None):
    prev = prev or {}
    board = board or {}
    waimai = waimai or {}
    tuango = tuango or {}

    dst["level"] = show(summary.get("城市等级"), dst.get("level") or "—")
    city_type = show(summary.get("城市类型") or board.get("城市类型"), dst.get("type") or "")
    if board.get("城市类型"):
        city_type = show(board.get("城市类型"), city_type)
    dst["type"] = city_type or dst.get("type") or "—"
    dst["hasTuango"] = "团购" in str(dst["type"])
    dst["account"] = show(board.get("账号编号"), dst.get("account") or dst["name"])
    dst["dataDate"] = show(summary.get("日期"), "")[:10]
    dst["riskRoll"] = show(board.get("风险状态（滚动加权）"), dst.get("riskRoll") or "—")
    dst["riskMonth"] = show(board.get("风险状态(当月)"), dst.get("riskMonth") or "—")
    dst["warnWeighted"] = show(summary.get("加权排名区间") or board.get("加权预警"), "无预警")
    dst["warnMarket"] = show(summary.get("大盘预警") or board.get("大盘预警"), "—")
    dst["warnDelta"] = show(board.get("预警状态环比变化"), None) or band_delta(prev.get("大盘预警"), summary.get("大盘预警")) or "—"

    dst["cluster"] = {
        "waimai": show(summary.get("外卖能力分群"), "无分群"),
        "tuango": show(summary.get("团购能力分群"), "无分群"),
        "lvyue": show(summary.get("履约能力分群"), "无分群"),
        "lingshou": show(summary.get("零售能力分群"), "无分群"),
        "zuzhi": show(summary.get("组织能力分群"), "无分群"),
        "shangye": show(summary.get("商业增值分群_外卖") or summary.get("用户体验分群"), "无分群"),
        "tiyan": show(summary.get("用户体验分群"), "无分群"),
        "zhili": show(summary.get("综合治理分群"), "无分群"),
    }

    band_map = {
        "外卖": ("外卖能力预警", "外卖模块"),
        "团购": ("团购能力预警", "团购模块"),
        "履约": ("履约能力预警", "履约模块"),
        "零售": ("零售能力预警", "零售模块"),
        "组织": ("组织能力预警", "组织模块"),
        "商业增值": ("商业增值能力预警", "商业增值"),
        "用户体验": ("用户体验能力预警", "用户体验"),
        "综合治理": ("综合治理能力预警", "综合治理"),
    }
    bands = {}
    mod_warn_delta = {}
    for cn, (sk, bk) in band_map.items():
        val = summary.get(sk)
        if blank(val) and board:
            val = board.get(bk)
        if cn == "团购" and not dst["hasTuango"]:
            bands[cn] = "不预警"
            mod_warn_delta[cn] = None
            continue
        bands[cn] = show(val, "—")
        mod_warn_delta[cn] = band_delta(prev.get(sk), val)
    dst["bands"] = bands

    def wd(mod):
        return mod_warn_delta.get(mod)

    # 指标值：不考核的市场开发率按源表展示
    wm_order_val = summary.get("市场开发率（订单）指标值-外卖")
    wm_order_band = summary.get("市场开发率（订单）-外卖")
    wm_gtv_val = summary.get("市场开发率（实付）指标值-外卖")
    wm_gtv_band = summary.get("市场开发率（实付）-外卖")

    details = {
        "外卖": {
            "市场开发率(订单量)": metric(
                wm_order_val,
                wm_order_band,
                fmt_pp(board.get("期环比-市场开发率（订单）")),
                None if is_na_band(wm_order_band) else wd("外卖"),
            ),
            "市场开发率(GTV)": metric(
                wm_gtv_val,
                wm_gtv_band,
                fmt_pp(board.get("期环比-市场开发率（实付）")),
                None if is_na_band(wm_gtv_band) else wd("外卖"),
            ),
            "餐饮商家渗透率": metric(
                summary.get("餐饮商家渗透率指标值-外卖") or summary.get("餐饮商家渗透率"),
                summary.get("餐饮商家渗透率-外卖"),
                fmt_pp(board.get("期环比-餐饮商家渗透率")),
                wd("外卖"),
            ),
            "月交易商家数": metric(waimai.get("交易商家数"), value_delta=None),
            "月在线商家数": metric(waimai.get("公海商家数"), value_delta=None),
            "月动销率": metric(waimai.get("餐饮渗透率"), value_delta=fmt_pp(waimai.get("餐饮渗透率期环比"))),
        },
        "零售": {
            "日均零售 YOY": metric(
                summary.get("YoY指标值-零售") or summary.get("日均零售YOY"),
                summary.get("YoY-零售预警"),
                fmt_pp(board.get("期环比-零售YoY")),
                wd("零售"),
            ),
            "优质仓数达标情况": metric(summary.get("优质仓数达标情况")),
        },
        "团购": {
            "团购市场开发率": metric(
                "—" if not dst["hasTuango"] else (summary.get("市场开发率指标值-团购") or summary.get("团购市场开发率GAP")),
                "不预警" if not dst["hasTuango"] else summary.get("市场开发率-团购"),
                "—" if not dst["hasTuango"] else fmt_pp(board.get("期环比-团购市场开发率") or tuango.get("本月市场开发率期环比")),
                None if not dst["hasTuango"] else wd("团购"),
            ),
            "优质商家渗透率": metric(
                "—" if not dst["hasTuango"] else (summary.get("优质商家渗透率指标值-团购") or summary.get("优质商家渗透率") or summary.get("4N_1动销率")),
                "不预警" if not dst["hasTuango"] else summary.get("优质商家渗透率-团购"),
                "—" if not dst["hasTuango"] else fmt_pp(board.get("期环比-团购优质商家渗透率") or tuango.get("优质商家渗透率期环比")),
                None if not dst["hasTuango"] else wd("团购"),
            ),
            "4n+1货架达标数": metric("—"),
            "4n+1达标商家动销数": metric("—" if not dst["hasTuango"] else tuango.get("4N+1动销商家数")),
            "整体商家数": metric("—" if not dst["hasTuango"] else tuango.get("整体商家数")),
            "智能点餐占比": metric("—" if not dst["hasTuango"] else (tuango.get("智能点餐占比") or summary.get("智能点餐占比"))),
        },
        "履约": {
            "推单完成率": metric(
                summary.get("推单完成率指标值-履约") or summary.get("推单完成率"),
                summary.get("推单完成率排名-履约"),
                fmt_pp(board.get("期环比-推单完成率")),
                wd("履约"),
            ),
            "压力天出勤率": metric(summary.get("压力天出勤率")),
            "超45分钟订单占比": metric(
                summary.get("超45分钟订单占比指标值-履约") or summary.get("超45分钟订单占比"),
                summary.get("超45分钟订单占比-履约"),
                fmt_pp(board.get("期环比-超45分钟订单占比")),
                wd("履约"),
            ),
        },
        "用户体验": {
            "用户投诉商家问题万服排名": metric(
                summary.get("用户商家万服分群排名") or summary.get("用户体验_用户投诉商家问题万服差值"),
                summary.get("用户体验_用户投诉商家问题万服差值排名"),
                fmt_num_delta(board.get("期环比-用户投诉商家问题万服")),
                wd("用户体验"),
            ),
            "用户投诉履约问题万服排名": metric(
                summary.get("用户履约万服分群排名") or summary.get("用户体验_用户投诉履约问题万服差值"),
                summary.get("用户体验_用户投诉履约问题万服差值排名"),
                fmt_num_delta(board.get("期环比-用户投诉履约问题万服")),
                wd("用户体验"),
            ),
        },
        "组织": {
            "外卖BD满编率": metric(summary.get("外卖BD满编率")),
            "团购BD满编率": metric(summary.get("团购BD满编率")),
            "外卖BD效能": metric(summary.get("外卖BD效能(件)")),
            "团购BD效能": metric(summary.get("团购BD效能（件）")),
            "高效能BD流失率": metric(summary.get("高效能人员流失率")),
            "关键岗位认证通过率(城)": metric(summary.get("关键岗位认证通过率(得分)")),
            "关键岗位认证通过率(商)": metric("—"),
            "外卖BD件均成本": metric(summary.get("BD件均做工成本")),
        },
        "商业增值": {
            "外卖货币化率": metric(
                summary.get("外卖货币化率指标值-商业增值") or summary.get("外卖货币化率"),
                summary.get("商业增值_外卖货币化率排名"),
                fmt_pp(board.get("期环比-货币化率")),
                wd("商业增值"),
            ),
            "团购货币化率": metric(
                "—" if not dst["hasTuango"] else (summary.get("团购货币化率指标值-商业增值") or summary.get("团购货币化率")),
                "不预警" if not dst["hasTuango"] else summary.get("商业增值_团购货币化率排名"),
                None,
                None if not dst["hasTuango"] else wd("商业增值"),
            ),
        },
        "综合治理": {
            "月外卖虚假业绩占比": metric(summary.get("月外卖虚假业绩占比"), summary.get("综合治理能力预警")),
            "月团购虚假业绩占比": metric("—" if not dst["hasTuango"] else summary.get("月团购虚假业绩占比")),
            "月异常骑手率": metric(summary.get("月异常骑手率")),
            "安全事件扣分情况": metric("—"),
        },
    }
    # 团购货币化率排名为 0 时视为不预警
    tg_mon = details["商业增值"]["团购货币化率"]
    if show(tg_mon.get("band")) in {"0", "0.0"}:
        tg_mon["band"] = "不预警"
    dst["details"] = details
    dst["mom"] = {
        "市场开发率(订单)": fmt_pp(board.get("期环比-市场开发率（订单）")),
        "市场开发率(实付)": fmt_pp(board.get("期环比-市场开发率（实付）")),
        "餐饮渗透率": fmt_pp(board.get("期环比-餐饮商家渗透率")),
        "团购市场开发率": "—" if not dst["hasTuango"] else fmt_pp(board.get("期环比-团购市场开发率")),
        "团购优质渗透率": "—" if not dst["hasTuango"] else fmt_pp(board.get("期环比-团购优质商家渗透率")),
        "推单完成率": fmt_pp(board.get("期环比-推单完成率")),
        "超45分钟占比": fmt_pp(board.get("期环比-超45分钟订单占比")),
        "零售YoY": fmt_pp(board.get("期环比-零售YoY")),
        "货币化率": fmt_pp(board.get("期环比-货币化率")),
        "商家万服": fmt_num_delta(board.get("期环比-用户投诉商家问题万服")),
        "履约万服": fmt_num_delta(board.get("期环比-用户投诉履约问题万服")),
    }


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
    payload = json.loads(html[start:end])
    return start, end, payload


def fetch_metabase():
    CACHE.mkdir(parents=True, exist_ok=True)
    iso = latest_summary_date()
    day = iso[:10]
    # 上一期：日期参数里比本期更早的最大一天
    url = f"{MB_HOST}/api/public/dashboard/{MB_DASH_UUID}/params/fe957d70/values"
    days = sorted({v[0][:10] for v in (http_json(url).get("values") or [])})
    prev_day = next((d for d in reversed(days) if d < day), None)
    dump = {"periodDate": day, "prevDate": prev_day, "fetchedAt": datetime.now(timezone.utc).isoformat()}
    tables = {}
    for name, spec in CARDS.items():
        cols, rows = query_card(spec, iso)
        tables[name] = {"cols": cols, "rows": rows}
        dump[name] = {"cols": cols, "n": len(rows)}
        if name == "summary" and prev_day:
            pcols, prows = query_card(spec, prev_day + "T00:00:00+08:00")
            tables["summary_prev"] = {"cols": pcols, "rows": prows}
            dump["summary_prev"] = {"cols": pcols, "n": len(prows), "date": prev_day}
    (CACHE / "metabase_latest.json").write_text(json.dumps({"meta": dump, "tables": tables}, ensure_ascii=False), encoding="utf-8")
    return day, prev_day, tables


def main():
    day, prev_day, tables = fetch_metabase()
    tests = {"cityStats": [], "people": [], "totalRecords": 0, "totalPeople": 0}
    try:
        token = login()
        tests = summarize_tests(fetch_tests(token))
    except Exception as e:
        print("tests skipped:", e)

    summary = rows_to_city_map(tables["summary"]["cols"], tables["summary"]["rows"])
    prev = rows_to_city_map(tables.get("summary_prev", {}).get("cols") or [], tables.get("summary_prev", {}).get("rows") or [])
    board = pick_latest_board(tables["cityboard"]["cols"], tables["cityboard"]["rows"])
    waimai = rows_to_city_map(tables["waimai"]["cols"], tables["waimai"]["rows"])
    tuango = rows_to_city_map(tables["tuango"]["cols"], tables["tuango"]["rows"])

    missing = [c for c in CITIES if c not in summary]
    if missing:
        raise RuntimeError(f"模块数据汇总表缺少城市: {missing}; got {list(summary)}")

    html_path = HTMLS[0]
    html = html_path.read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)
    scraped_at = datetime.now(timezone.utc).isoformat()
    data.setdefault("meta", {})
    data["meta"]["period"] = f"{day[:4]}年{int(day[5:7])}月"
    data["meta"]["dataDate"] = day
    data["meta"]["prevPeriod"] = prev_day
    data["meta"]["scrapedAt"] = scraped_at
    data["meta"]["testSyncAt"] = scraped_at
    data["meta"]["obsTitle"] = "新商考核 / 模块数据汇总表"
    data["meta"]["obsUpdatedAt"] = day
    data["meta"]["richObsCount"] = None
    data["meta"]["richCz1Count"] = len(CITIES)
    data["tests"] = tests
    data["source"] = {
        "adminUrl": ADMIN_PAGE,
        "dashboard": "新商考核",
        "tab": "模块数据汇总表",
        "metabase": f"{MB_HOST}/public/dashboard/{MB_DASH_UUID}",
        "periodDate": day,
        "prevDate": prev_day,
        "tests": COLLECTION,
    }

    by_name = {c["name"]: c for c in (data.get("cities") or [])}
    new_cities = []
    for name in CITIES:
        city = by_name.get(name) or {"name": name}
        city["name"] = name
        apply_city(city, summary[name], prev.get(name), board.get(name), waimai.get(name), tuango.get(name))
        new_cities.append(city)
    data["cities"] = new_cities

    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = html[:start] + new_json + html[end:]
    new_html = new_html.replace(
        'const NO_WARN = new Set(["—", "不预警", "暂不预警", "无预警", "不考核", "", null, undefined]);',
        'const NO_WARN = new Set(["—", "不预警", "暂不预警", "无预警", "不考核", "数据准备中", "不适用", "", null, undefined]);',
    )
    footer_old = "能力指标同步自初心「新商评观测」（2026-07-27）；测评成绩实时拉取集合「新商评测试结果」· 川藏一区"
    footer_new = f"能力指标同步自初心「新商考核 / 模块数据汇总表」（{day}）；测评成绩另见集合「新商评测试结果」"
    new_html = new_html.replace(footer_old, footer_new)
    new_html = new_html.replace(
        "能力指标同步自初心「新商评观测」（2026-07-27）；测评成绩实时拉取集合「新商评测试结果」· 川藏一区",
        footer_new,
    )
    for p in HTMLS:
        p.write_text(new_html, encoding="utf-8")
        print("wrote", p)

    print(
        json.dumps(
            {
                "ok": True,
                "date": day,
                "prev": prev_day,
                "cities": {
                    n: {
                        "level": summary[n].get("城市等级"),
                        "market": summary[n].get("大盘预警"),
                        "waimai": summary[n].get("外卖能力预警"),
                    }
                    for n in CITIES
                },
                "tests": tests.get("totalRecords"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
