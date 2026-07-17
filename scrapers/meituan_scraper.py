"""美团看板 CDP 抓取核心：连接 Chrome → 拉 API / 嗅探网络 / 解析表格 → 入库。"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Iterable, Optional

import db
from config import CITIES
from scrapers._common import now, today, write_status
from scrapers.cdp_client import CDPError, CDPSession, connect_tab
from scrapers.meituan_config import CHROME_CDP_PORT, TAB_URL_PATTERNS, city_aliases, load_endpoints


def active_city() -> Optional[str]:
    city = os.environ.get("MEITUAN_ACTIVE_CITY", "").strip()
    return city if city in CITIES else None


def _apply_active_city(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每个 Chrome 资料通常只对应一城，页面上可能没有城市列。"""
    ac = active_city()
    if not ac:
        return records
    out = []
    for rec in records:
        item = dict(rec)
        if not item.get("city") or item.get("city") not in CITIES:
            item["city"] = ac
        out.append(item)
    if not out and ac:
        out.append({"city": ac})
    return out


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _parse_number(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = _norm(val).replace(",", "").replace("%", "")
    if not s or s in {"—", "-", "null", "None"}:
        return None
    try:
        if s.endswith("%"):
            return float(s[:-1]) / 100
        return float(s)
    except ValueError:
        return None


def _match_city(text: str, aliases: dict[str, list[str]]) -> Optional[str]:
    t = _norm(text)
    for city, names in aliases.items():
        for name in names:
            if name and name in t:
                return city
    return None


def _find_col(headers: list[str], candidates: list[str]) -> Optional[int]:
    lowered = [h.lower() for h in headers]
    for cand in candidates:
        c = cand.lower()
        for i, h in enumerate(lowered):
            if c in h or h in c:
                return i
    return None


def _rows_from_tables(tables: list[dict], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    colmap = cfg.get("table_column_map") or {}
    aliases = city_aliases(cfg)
    out: list[dict[str, Any]] = []
    for table in tables:
        headers = table.get("headers") or []
        for row in table.get("rows") or []:
            if not row:
                continue
            city_idx = _find_col(headers, colmap.get("city", []))
            city = None
            if city_idx is not None and city_idx < len(row):
                city = _match_city(row[city_idx], aliases)
            if not city:
                city = _match_city(" ".join(row), aliases)
            if not city:
                continue
            item: dict[str, Any] = {"city": city}
            mapping = {
                "score": colmap.get("score", []),
                "target": colmap.get("target", []),
                "achievement": colmap.get("achievement", []),
                "metric_key": colmap.get("metric_key", []),
                "metric_value": colmap.get("metric_value", []),
                "todo_name": colmap.get("todo_name", []),
                "status": colmap.get("status", []),
                "progress": colmap.get("progress", []),
                "title": colmap.get("title", []),
                "content": colmap.get("content", []),
                "published_at": colmap.get("published_at", []),
            }
            for key, cands in mapping.items():
                idx = _find_col(headers, cands)
                if idx is not None and idx < len(row):
                    val = row[idx]
                    if key in {"score", "target", "achievement", "metric_value", "progress"}:
                        item[key] = _parse_number(val)
                    else:
                        item[key] = _norm(val)
            out.append(item)
    return out


def _walk_json(node: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            yield p, v
            yield from _walk_json(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_json(v, f"{path}[{i}]")


def _extract_city_records(payload: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    aliases = city_aliases(cfg)
    found: list[dict[str, Any]] = []

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            text_blob = json.dumps(obj, ensure_ascii=False)
            city = None
            for key in ("city", "cityName", "city_name", "orgName", "regionName", "areaName"):
                if key in obj:
                    city = _match_city(str(obj[key]), aliases)
                    if city:
                        break
            if not city:
                city = _match_city(text_blob, aliases)
            if city:
                rec = {"city": city}
                for k, v in obj.items():
                    lk = k.lower()
                    if any(x in lk for x in ("score", "kpi", "point")) and isinstance(v, (int, float, str)):
                        rec.setdefault("score", _parse_number(v))
                    if "target" in lk:
                        rec.setdefault("target", _parse_number(v))
                    if any(x in lk for x in ("achieve", "rate", "ratio", "complete")):
                        rec.setdefault("achievement", _parse_number(v))
                    if any(x in lk for x in ("gmv", "value", "amount", "metric")) and isinstance(v, (int, float, str)):
                        rec.setdefault("metric_value", _parse_number(v))
                    if lk in {"metric", "metrickey", "indicator", "indexname", "name"} and isinstance(v, str):
                        rec.setdefault("metric_key", _norm(v))
                    if any(x in lk for x in ("title", "subject")):
                        rec.setdefault("title", _norm(v))
                    if any(x in lk for x in ("content", "summary", "desc")):
                        rec.setdefault("content", _norm(v))
                    if any(x in lk for x in ("status", "state")):
                        rec.setdefault("status", _norm(v))
                    if "progress" in lk:
                        rec.setdefault("progress", _parse_number(v))
                    if any(x in lk for x in ("todo", "task", "requirement")) and isinstance(v, str):
                        rec.setdefault("todo_name", _norm(v))
                    if any(x in lk for x in ("time", "date", "publish")):
                        rec.setdefault("published_at", _norm(v)[:19])
                if len(rec) > 1:
                    found.append(rec)
            for v in obj.values():
                visit(v)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(payload)
    # 去重
    uniq = []
    seen = set()
    for rec in found:
        key = tuple(sorted(rec.items()))
        if key not in seen:
            seen.add(key)
            uniq.append(rec)
    return uniq


def _try_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def collect_payloads(
    session: CDPSession,
    page_key: str,
    keywords: list[str],
    cfg: Optional[dict[str, Any]] = None,
) -> tuple[list[Any], list[str]]:
    cfg = cfg or load_endpoints()
    pages = cfg.get("pages") or {}
    page_url = pages.get(page_key) or pages.get("dashboard")
    logs: list[str] = []
    payloads: list[Any] = []

    if page_url:
        session.navigate(page_url, wait_sec=4.0)
        logs.append(f"已打开页面: {page_url}")

    for url in cfg.get("api_fetch_urls") or []:
        try:
            resp = session.fetch_json_in_page(url)
            if isinstance(resp, dict) and resp.get("data") is not None:
                payloads.append(resp["data"])
                logs.append(f"fetch 成功: {url}")
            elif isinstance(resp, dict) and resp.get("status") == 200:
                payloads.append(resp)
                logs.append(f"fetch 返回: {url}")
            else:
                logs.append(f"fetch 无数据: {url} -> {str(resp)[:200]}")
        except CDPError as exc:
            logs.append(f"fetch 失败: {url} -> {exc}")

    def url_match(u: str) -> bool:
        u_low = u.lower()
        return any(k.lower() in u_low for k in keywords)

    captured = session.capture_responses(url_match, duration_sec=18.0, reload=True)
    for item in captured:
        data = _try_json_loads(item.body)
        if data is not None:
            payloads.append(data)
            logs.append(f"network JSON: {item.url[:120]}")
        elif any(k in item.url for k in keywords):
            logs.append(f"network 非JSON: {item.url[:120]}")

    tables = session.scrape_dom_tables()
    if tables:
        rows = _rows_from_tables(tables, cfg)
        if rows:
            payloads.append({"__tables__": rows})
            logs.append(f"DOM 表格解析 {len(rows)} 行")

    return payloads, logs


def _collect_records(payloads: list[Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    all_records: list[dict[str, Any]] = []
    for payload in payloads:
        if isinstance(payload, dict) and "__tables__" in payload:
            all_records.extend(payload["__tables__"])
        else:
            all_records.extend(_extract_city_records(payload, cfg))
    return _apply_active_city(all_records)


def save_dashboard(payloads: list[Any], cfg: dict[str, Any]) -> int:
    ts = now()
    date = today()
    n = 0
    all_records = _collect_records(payloads, cfg)

    metric_rows = []
    for rec in all_records:
        city = rec.get("city")
        if city not in CITIES:
            continue
        if rec.get("metric_value") is not None or rec.get("metric_key"):
            metric_rows.append(
                (
                    city,
                    date,
                    _norm(rec.get("metric_key") or "gmv"),
                    rec.get("metric_value") or rec.get("score"),
                    None,
                    ts,
                )
            )
        elif rec.get("score") is not None:
            metric_rows.append((city, date, "kpi_score", rec.get("score"), None, ts))

    n += db.upsert_many(
        """INSERT OR REPLACE INTO dashboard_metrics
           (city, metric_date, metric_key, metric_value, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        metric_rows,
    )
    snapshot = {"date": date, "active_city": active_city(), "payloads": payloads, "records": all_records}
    db.upsert_many(
        """INSERT OR REPLACE INTO dashboard_snapshots
           (snapshot_date, payload_json, updated_at)
           VALUES (?, ?, ?)""",
        [(date, json.dumps(snapshot, ensure_ascii=False), ts)],
    )
    return n


def save_kpi_scores(
    payloads: list[Any],
    cfg: dict[str, Any],
    table: str,
    catering: bool = True,
) -> int:
    ts = now()
    date = today()
    rows = []
    all_records = _collect_records(payloads, cfg)
    for rec in all_records:
        city = rec.get("city")
        if city not in CITIES:
            continue
        score = rec.get("score")
        target = rec.get("target")
        ach = rec.get("achievement")
        if score is None and rec.get("metric_value") is not None:
            score = rec.get("metric_value")
        if score is None and target is None:
            continue
        if ach is None and score is not None and target:
            ach = score / target if target else None
        rows.append((city, date, score, target, ach, None, ts))

    if table == "catering":
        sql = """INSERT OR REPLACE INTO catering_daily_scores
                 (city, metric_date, score, target, achievement, extra_json, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""
    else:
        sql = """INSERT OR REPLACE INTO non_catering_daily_scores
                 (city, metric_date, score, target, achievement, extra_json, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""
    return db.upsert_many(sql, rows)


def save_todos(payloads: list[Any], cfg: dict[str, Any]) -> int:
    ts = now()
    date = today()
    rows = []
    all_records = _collect_records(payloads, cfg)
    for rec in all_records:
        city = rec.get("city")
        if city not in CITIES:
            continue
        name = rec.get("todo_name") or rec.get("title")
        if not name:
            continue
        rows.append(
            (
                city,
                date,
                name,
                rec.get("status") or "未知",
                rec.get("progress"),
                None,
                ts,
            )
        )
    return db.upsert_many(
        """INSERT OR REPLACE INTO todo_achievements
           (city, todo_date, todo_name, status, progress, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def save_notices(payloads: list[Any], cfg: dict[str, Any]) -> int:
    ts = now()
    rows = []
    seq = 0
    for rec in _collect_records(payloads, cfg):
        title = rec.get("title") or rec.get("todo_name")
        if not title:
            continue
        seq += 1
        notice_id = f"cdp-{today()}-{seq}"
        rows.append(
            (
                notice_id,
                title,
                rec.get("published_at") or today(),
                rec.get("content") or title,
                "",
                ts,
            )
        )
    return db.upsert_many(
        """INSERT OR REPLACE INTO meituan_notices
           (notice_id, title, published_at, content, source_url, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )


def run_scrape(
    name: str,
    page_key: str,
    keyword_key: str,
    saver,
    catering_filter: Optional[bool] = None,
) -> int:
    db.init_db()
    cfg = load_endpoints()
    keywords = (cfg.get("network_keywords") or {}).get(keyword_key, [])
    logs: list[str] = []
    try:
        session = connect_tab(CHROME_CDP_PORT, TAB_URL_PATTERNS)
    except CDPError as exc:
        write_status(name, {"ok": False, "error": str(exc)})
        db.log_sync(name, "fail", str(exc))
        print(str(exc))
        return 1
    try:
        payloads, logs = collect_payloads(session, page_key, keywords, cfg)
        if catering_filter is True:
            payloads = [p for p in payloads if True]  # same source, saver filters
        if not payloads:
            msg = "未抓到数据。请确认 Chrome 已登录美团看板，并在 meituan_endpoints.json 配置 pages / api_fetch_urls"
            write_status(name, {"ok": False, "message": msg, "logs": logs})
            db.log_sync(name, "fail", msg)
            print(msg)
            return 1
        if catering_filter is None:
            count = saver(payloads, cfg)
        elif catering_filter is True:
            count = saver(payloads, cfg, "catering")
        else:
            count = saver(payloads, cfg, "non_catering")
        msg = f"写入 {count} 行"
        write_status(name, {"ok": True, "rows": count, "logs": logs})
        db.log_sync(name, "ok", msg)
        print(msg)
        return 0
    except CDPError as exc:
        write_status(name, {"ok": False, "error": str(exc), "logs": logs})
        db.log_sync(name, "fail", str(exc))
        print(str(exc))
        return 1
    finally:
        session.close()
