"""从初心后台拉取川藏一区新商评数据，写回详表看板 DATA。"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://www.chuxin.city"
COLLECTION = "t_t6e991yzf4c"
REGION = "川藏一区"
CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
ROOT = Path(__file__).resolve().parents[1]
HTMLS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]

SKIP_METRICS = ("模块得分", "组织效率得分", "城市类型", "综合治理得分")
NAME_MAP = {
    "优质仓数达标": "优质仓数达标情况",
    "商家问题万服排名": "用户投诉商家问题万服排名",
    "履约问题万服排名": "用户投诉履约问题万服排名",
    "月外卖虚假业绩": "月外卖虚假业绩占比",
    "月团购虚假业绩": "月团购虚假业绩占比",
    "异常骑手率": "月异常骑手率",
    "关键岗位认证(城)": "关键岗位认证通过率(城)",
    "BD件均成本": "外卖BD件均成本",
}


def req(path, token=None, method="GET", data=None, params=None):
    if params:
        path += ("&" if "?" in path else "?") + urllib.parse.urlencode(params, doseq=True)
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def download(url, token):
    request = urllib.request.Request(BASE + url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=180) as resp:
        return resp.read()


def login():
    data = req("/api/auth:signIn", method="POST", data={"account": "qiaoxianhai", "password": "123"})
    token = (data.get("data") or {}).get("token")
    if not token:
        raise RuntimeError(f"login failed: {data}")
    return token


def fetch_tests(token):
    items = []
    page = 1
    while True:
        data = req(
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


def fetch_obs_cities(token):
    hp = req("/api/html_pages:list", token, params={"pageSize": 20, "sort[]": "-updatedAt", "appends[]": "html_file"})
    pages = hp.get("data") or []
    page = next((p for p in pages if p.get("title") == "新商评观测"), None)
    meta = {"title": None, "fileUpdatedAt": None, "fileUrl": None}
    if not page or not page.get("html_file"):
        return [], meta
    f0 = page["html_file"][0]
    meta.update({"title": page.get("title"), "fileUpdatedAt": f0.get("updatedAt"), "fileUrl": f0.get("url")})
    html = download(f0["url"], token).decode("utf-8", "replace")
    # write temp js and eval via extracting object — already have node from previous run;
    # parse with a small node script
    start = html.find("const DATA")
    brace = html.find("{", start)
    depth = 0
    in_str = None
    esc = False
    end = None
    for j, ch in enumerate(html[brace:], brace):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    blob = html[brace:end]
    tmp = ROOT / "data" / "xinshang"
    tmp.mkdir(parents=True, exist_ok=True)
    js_path = tmp / "_obs_eval.js"
    out_path = tmp / "_obs.json"
    js_path.write_text("const DATA = " + blob + ";\nprocess.stdout.write(JSON.stringify(DATA));\n", encoding="utf-8")
    import subprocess

    subprocess.check_call(["node", str(js_path)], stdout=out_path.open("w", encoding="utf-8"))
    data = json.loads(out_path.read_text(encoding="utf-8"))
    js_path.unlink(missing_ok=True)
    out_path.unlink(missing_ok=True)
    return data.get("cities") or [], meta


def fetch_rich_cz1(token):
    hp = req("/api/html_pages:list", token, params={"pageSize": 20, "sort[]": "-updatedAt", "appends[]": "html_file"})
    page = next((p for p in (hp.get("data") or []) if p.get("title") == "新商能力评价"), None)
    if not page or not page.get("html_file"):
        return [], {}
    f0 = page["html_file"][0]
    html = download(f0["url"], token).decode("utf-8", "replace")
    idx = html.find('"cities"')
    if idx < 0:
        return [], {"title": page.get("title"), "fileUpdatedAt": f0.get("updatedAt")}
    start = html.find("[", idx)
    cities, _ = json.JSONDecoder().raw_decode(html[start:])
    cz1 = [c for c in cities if c.get("name") in CITIES or "川藏一区" in str(c.get("regionSource") or "")]
    return cz1, {"title": page.get("title"), "fileUpdatedAt": f0.get("updatedAt"), "fileUrl": f0.get("url"), "allCount": len(cities)}


def fmt_pct_if_number(val):
    if val is None or val == "—":
        return val
    s = str(val).strip()
    if s.endswith("%"):
        return s
    try:
        float(s)
        if "." in s and float(s) <= 100:
            # 认证通过率 obs 给 99.63 无百分号
            return s + "%"
    except ValueError:
        pass
    return s


def apply_obs_details(dst_details, obs_city):
    for mod, rows in (obs_city.get("details") or {}).items():
        bucket = dst_details.setdefault(mod, {})
        for row in rows:
            name = row[0] if row else ""
            if not name or any(k in name for k in SKIP_METRICS):
                continue
            value = row[1] if len(row) > 1 else "—"
            band = row[2] if len(row) > 2 else None
            if name == "外卖/团购满编率" and " / " in str(value):
                a, b = [x.strip() for x in str(value).split(" / ", 1)]
                bucket["外卖BD满编率"] = {"value": a}
                bucket["团购BD满编率"] = {"value": b}
                continue
            if name == "外卖/团购BD效能" and " / " in str(value):
                a, b = [x.strip() for x in str(value).split(" / ", 1)]
                bucket["外卖BD效能"] = {"value": a}
                bucket["团购BD效能"] = {"value": b}
                continue
            if name.startswith("安全得分"):
                # "2.5 / 0"
                deduct = str(value).split("/")[-1].strip() if value else "0"
                bucket["安全事件扣分情况"] = {"value": "无扣分" if deduct in ("0", "0.0", "") else f"扣分 {deduct}"}
                continue
            mapped = NAME_MAP.get(name, name)
            if mapped == "关键岗位认证通过率(城)":
                value = fmt_pct_if_number(value)
            elif mapped == "月团购虚假业绩占比" and str(value) == "0":
                value = "0%"
            rec = {"value": value if value not in (None, "") else "—"}
            if band and band not in ("—",):
                rec["band"] = band
            bucket[mapped] = rec


def apply_rich_city(dst, rich):
    board = rich.get("board") or {}
    mw = board.get("moduleWarn") or {}
    mwc = board.get("moduleWarnChange") or {}
    mod_map = {
        "waimai": "外卖",
        "tuangou": "团购",
        "fulfillment": "履约",
        "retail": "零售",
        "org": "组织",
        "commercial": "商业增值",
        "experience": "用户体验",
        "governance": "综合治理",
    }
    if board.get("riskStatus"):
        dst["riskRoll"] = board.get("riskStatus")
    if board.get("overallWarn"):
        dst["warnMarket"] = board["overallWarn"]
    if board.get("warnChange"):
        dst["warnDelta"] = board["warnChange"]
    bands = dst.setdefault("bands", {})
    for k, cn in mod_map.items():
        if mw.get(k):
            bands[cn] = mw[k]
        change = mwc.get(k)
        # stamp warn delta onto metrics of that module later
        dst.setdefault("_modWarnDelta", {})[cn] = change
    ind = rich.get("indicators") or {}
    ind_map = {
        "orderDevRate": ("外卖", "市场开发率(订单量)"),
        "payDevRate": ("外卖", "市场开发率(GTV)"),
        "cateringPenetration": ("外卖", "餐饮商家渗透率"),
        "tgDevRate": ("团购", "团购市场开发率"),
        "qualityMerchantPenetration": ("团购", "优质商家渗透率"),
        "pushCompleteRate": ("履约", "推单完成率"),
        "over45TimeoutShare": ("履约", "超45分钟订单占比"),
        "retailYoy": ("零售", "日均零售 YOY"),
        "monetizationRate": ("商业增值", "外卖货币化率"),
        "complaintMerchantDelta": ("用户体验", "用户投诉商家问题万服排名"),
        "complaintFulfillDelta": ("用户体验", "用户投诉履约问题万服排名"),
    }
    details = dst.setdefault("details", {})
    for key, (mod, name) in ind_map.items():
        rec = ind.get(key) or {}
        if not rec:
            continue
        val = rec.get("value")
        unit = rec.get("unit") or ""
        shown = "—" if val is None else (f"{val}{unit}" if unit and not str(val).endswith(unit) else str(val) + ("" if unit == "%" or str(val).endswith("%") else ""))
        if unit == "%" and val is not None and not str(shown).endswith("%"):
            shown = f"{val}%"
        item = details.setdefault(mod, {}).setdefault(name, {})
        if val is not None:
            item["value"] = shown
        if rec.get("rankBand"):
            item["band"] = rec["rankBand"]
        if rec.get("change"):
            item["valueDelta"] = rec["change"]
            item["delta"] = rec["change"]  # warn delta fallback if same period movement
        if rec.get("valueDelta") is not None and not rec.get("change"):
            item["mom"] = rec["valueDelta"]
    cat = rich.get("cateringActiveDaily") or {}
    if cat:
        waimai = details.setdefault("外卖", {})
        if cat.get("activeCount") is not None:
            waimai["月交易商家数"] = {"value": str(cat["activeCount"]), "valueDelta": cat.get("activeDelta")}
        if cat.get("onlineTotal") is not None:
            waimai["月在线商家数"] = {"value": str(cat["onlineTotal"]), "valueDelta": cat.get("onlineDelta")}
        if cat.get("rate") is not None:
            waimai["月动销率"] = {"value": f"{cat['rate']}%", "valueDelta": cat.get("rateDelta")}
    q = rich.get("qualityMerchant4n1") or {}
    if q.get("applicable"):
        tg = details.setdefault("团购", {})
        if q.get("active4n1") is not None:
            tg["4n+1达标商家动销数"] = {"value": str(q["active4n1"]), "valueDelta": q.get("activeDelta")}
        if q.get("totalMerchants") is not None:
            tg["整体商家数"] = {"value": str(q["totalMerchants"])}
        # 货架达标数：用当月里程碑目标作为「4n+1货架达标数」近似（源字段 targetActive）
        ms = ((q.get("targets") or {}).get("finalMilestone") or {}).get("targetActive")
        if ms is not None:
            tg["4n+1货架达标数"] = {"value": str(ms)}
    # attach module warn change to metrics that have bands
    for mod, change in (dst.get("_modWarnDelta") or {}).items():
        if not change:
            continue
        for _n, item in (details.get(mod) or {}).items():
            if isinstance(item, dict) and item.get("band"):
                item["delta"] = change
    dst.pop("_modWarnDelta", None)
    if board.get("dataDate"):
        dst["dataDate"] = board["dataDate"]


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


def main():
    token = login()
    tests_raw = fetch_tests(token)
    tests = summarize_tests(tests_raw)
    obs_cities, obs_meta = fetch_obs_cities(token)
    rich_cities, rich_meta = fetch_rich_cz1(token)
    scraped_at = datetime.now(timezone.utc).isoformat()

    html_path = HTMLS[0]
    html = html_path.read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)

    data.setdefault("meta", {})
    data["meta"]["scrapedAt"] = scraped_at
    data["meta"]["testSyncAt"] = scraped_at
    data["meta"]["obsTitle"] = obs_meta.get("title")
    data["meta"]["obsUpdatedAt"] = obs_meta.get("fileUpdatedAt")
    data["meta"]["richObsCount"] = rich_meta.get("allCount")
    data["meta"]["richCz1Count"] = len(rich_cities)
    if obs_cities:
        data["meta"]["period"] = "2026年7月"
        data["meta"]["dataDate"] = "2026-07-27"
    data["tests"] = tests
    data["source"] = {
        "adminUrl": f"{BASE}/v/admin/b7v8t424ohb",
        "tests": COLLECTION,
        "observation": obs_meta,
        "capabilityCabin": rich_meta,
    }

    obs_by = {c["name"]: c for c in obs_cities}
    rich_by = {c.get("name"): c for c in rich_cities}
    for city in data.get("cities") or []:
        name = city["name"]
        if name in obs_by:
            oc = obs_by[name]
            for k in ("level", "type", "hasTuango", "partnerId", "account", "riskRoll", "riskMonth", "warnWeighted", "warnMarket", "warnDelta", "bands"):
                if oc.get(k) is not None:
                    city[k] = oc[k]
            cl = city.setdefault("cluster", {})
            for k, v in (oc.get("cluster") or {}).items():
                cl[k] = v
            apply_obs_details(city.setdefault("details", {}), oc)
        if name in rich_by:
            apply_rich_city(city, rich_by[name])

    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = html[:start] + new_json + html[end:]
    # footer source note
    new_html = new_html.replace(
        "数据由川藏一区负责人统一更新 · 详表版 · 源表：新商考核体系 1.1（2026年7月）",
        "能力指标同步自初心「新商评观测」（2026-07-27）；测评成绩实时拉取集合「新商评测试结果」· 川藏一区",
    )
    for p in HTMLS:
        p.write_text(new_html, encoding="utf-8")
        print("wrote", p)

    print(
        json.dumps(
            {
                "ok": True,
                "tests": tests["totalRecords"],
                "obsCities": [c["name"] for c in obs_cities],
                "richCz1": [c.get("name") for c in rich_cities],
                "richAll": rich_meta.get("allCount"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
