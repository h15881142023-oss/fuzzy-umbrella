"""从初心 NocoBase 拉取川藏一区新商评数据。

数据源页面: http://www.chuxin.city/v/admin/b7v8t424ohb
- 集合 t_t6e991yzf4c（新商评测试结果）
- html_pages 中「新商能力评价」观测舱附件（能力预警详表，若含川藏一区则采用）
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "http://www.chuxin.city"
COLLECTION = "t_t6e991yzf4c"
REGION = "川藏一区"
CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
DEFAULT_ACCOUNT = "qiaoxianhai"
DEFAULT_PASSWORD = "123"

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "xinshang"


def _req(path: str, token: str | None = None, method: str = "GET", data: dict | None = None, params: dict | None = None) -> Any:
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
    with urllib.request.urlopen(request, timeout=120) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw)


def login(account: str = DEFAULT_ACCOUNT, password: str = DEFAULT_PASSWORD) -> str:
    # NocoBase basic authenticator accepts "account"
    payload = {"account": account, "password": password}
    data = _req("/api/auth:signIn", method="POST", data=payload)
    token = (data.get("data") or {}).get("token")
    if not token:
        raise RuntimeError(f"login failed: {data}")
    return token


def fetch_test_results(token: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        data = _req(
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
        meta = data.get("meta") or {}
        total_page = int(meta.get("totalPage") or 1)
        if page >= total_page:
            break
        page += 1
    # keep target cities primarily; retain other CZ1 cities for transparency
    return items


def _download(url_path: str, token: str) -> bytes:
    request = urllib.request.Request(
        BASE + url_path,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=180) as resp:
        return resp.read()


def fetch_observation_cities(token: str) -> tuple[list[dict], dict]:
    """从 html_pages「新商能力评价」附件解析 cities 数组。"""
    data = _req(
        "/api/html_pages:list",
        token,
        params={
            "pageSize": 20,
            "sort[]": "-updatedAt",
            "appends[]": "html_file",
            "filter": json.dumps({"title": "新商能力评价"}, ensure_ascii=False),
        },
    )
    pages = data.get("data") or []
    meta = {"pageTitle": None, "fileUrl": None, "fileUpdatedAt": None}
    if not pages:
        # fallback: latest html page with 新商 in title
        data = _req(
            "/api/html_pages:list",
            token,
            params={"pageSize": 20, "sort[]": "-updatedAt", "appends[]": "html_file"},
        )
        pages = [p for p in (data.get("data") or []) if "新商" in str(p.get("title") or "")]
    if not pages:
        return [], meta

    page = pages[0]
    meta["pageTitle"] = page.get("title")
    files = page.get("html_file") or []
    if not files:
        return [], meta
    f0 = files[0]
    url = f0.get("url") or f0.get("preview")
    meta["fileUrl"] = url
    meta["fileUpdatedAt"] = f0.get("updatedAt")
    if not url:
        return [], meta

    html = _download(url, token).decode("utf-8", "replace")
    idx = html.find('"cities":[')
    if idx < 0:
        idx = html.find('"cities": [')
    if idx < 0:
        return [], meta
    start = html.find("[", idx)
    cities, _ = json.JSONDecoder().raw_decode(html[start:])
    return cities, meta


def summarize_tests(rows: list[dict]) -> dict:
    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        city = r.get("cs") or "未知"
        by_city[city].append(r)

    city_stats = []
    for city in CITIES + sorted([c for c in by_city if c not in CITIES]):
        items = by_city.get(city, [])
        scores = [float(x["fs"]) for x in items if x.get("fs") is not None]
        # dedupe by person keep latest
        latest_by_person: dict[str, dict] = {}
        for x in sorted(items, key=lambda z: z.get("updatedAt") or "", reverse=True):
            name = (x.get("xm") or "").strip() or f"id-{x.get('id')}"
            if name not in latest_by_person:
                latest_by_person[name] = x
        latest_scores = [float(v["fs"]) for v in latest_by_person.values() if v.get("fs") is not None]
        low = [v for v in latest_by_person.values() if v.get("fs") is not None and float(v["fs"]) < 90]
        city_stats.append(
            {
                "city": city,
                "records": len(items),
                "people": len(latest_by_person),
                "avg": round(sum(latest_scores) / len(latest_scores), 2) if latest_scores else None,
                "min": min(latest_scores) if latest_scores else None,
                "max": max(latest_scores) if latest_scores else None,
                "below90": len(low),
                "latestAt": items[0].get("updatedAt") if items else None,
            }
        )

    people_rows = []
    for r in rows:
        people_rows.append(
            {
                "city": r.get("cs"),
                "name": r.get("xm"),
                "score": r.get("fs"),
                "note": r.get("bz"),
                "updatedAt": r.get("updatedAt"),
                "id": r.get("id"),
            }
        )

    return {
        "cityStats": city_stats,
        "people": people_rows,
        "totalRecords": len(rows),
        "totalPeopleApprox": sum(s["people"] for s in city_stats if s["city"] in CITIES),
    }


def filter_cz1_capability(cities: list[dict]) -> list[dict]:
    out = []
    for c in cities:
        name = c.get("name")
        region_source = str(c.get("regionSource") or "")
        region = str(c.get("region") or "")
        if name in CITIES or "川藏一区" in region_source or region_source == "川藏一区":
            out.append(c)
        elif "川藏一区" in region:
            out.append(c)
    return out


def scrape() -> dict:
    token = login()
    tests = fetch_test_results(token)
    obs_cities, obs_meta = fetch_observation_cities(token)
    cz1_cap = filter_cz1_capability(obs_cities)
    summary = summarize_tests(tests)
    payload = {
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "adminUrl": f"{BASE}/v/admin/b7v8t424ohb",
            "testCollection": COLLECTION,
            "region": REGION,
            "targetCities": CITIES,
            "observation": obs_meta,
        },
        "tests": summary,
        "capabilityCities": cz1_cap,
        "observationCityCount": len(obs_cities),
        # 不落盘 rawTests，减小体积并避免重复明细
    }
    return payload


def save_snapshot(payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"snapshot_{ts}.json"
    latest = OUT_DIR / "latest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest


def main() -> None:
    payload = scrape()
    path = save_snapshot(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "latest": str(path),
                "testRecords": payload["tests"]["totalRecords"],
                "capabilityCities": len(payload["capabilityCities"]),
                "observationCityCount": payload["observationCityCount"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
