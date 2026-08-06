"""川藏一区数据平台 — Flask 入口"""
from __future__ import annotations

import re
import subprocess
import sys
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

import db
from config import CITIES, PORT, PUBLIC_ORIGIN, REGION_NAME, SECRET_KEY, SITE_PASSWORD

BASE_DIR = Path(__file__).resolve().parent
SCRAPERS_DIR = BASE_DIR / "scrapers"

app = Flask(__name__)
app.secret_key = SECRET_KEY

NAV_ITEMS = [
    {"path": "/", "label": "首页"},
    {"path": "/kpi/catering", "label": "餐饮KPI"},
    {"path": "/kpi/non_catering", "label": "非餐KPI"},
    {"path": "/kpi/warning", "label": "城市警告"},
    {"path": "/kpi/delivery_fee", "label": "代补看板"},
    {"path": "/visit_check", "label": "拜访检核"},
    {"path": "/kpi/dashboard", "label": "绩效看板"},
    {"path": "/warning/catering", "label": "餐饮预警"},
    {"path": "/evaluation", "label": "合作商评价"},
    {"path": "/evaluation/xinshang", "label": "新商评价看板"},
    {"path": "/todo_achievement", "label": "TODO达成"},
    {"path": "/notice", "label": "通知函"},
    {"path": "/business", "label": "经营管理"},
    {"path": "/team", "label": "团队管理"},
]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    return {
        "region_name": REGION_NAME,
        "cities": CITIES,
        "nav_items": NAV_ITEMS,
        "public_origin": PUBLIC_ORIGIN,
        "current_path": request.path,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = (request.form.get("password") or "").strip()
        if password == SITE_PASSWORD:
            session["authenticated"] = True
            nxt = request.args.get("next") or "/"
            return redirect(nxt)
        error = "密码错误"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


def _data_page(title, api_endpoint, columns, sync_endpoint=None):
    return render_template(
        "data_page.html",
        title=title,
        api_endpoint=api_endpoint,
        sync_endpoint=sync_endpoint,
        columns=columns,
    )


@app.route("/kpi/catering")
@login_required
def page_kpi_catering():
    return _data_page(
        "餐饮 KPI 考核",
        "/api/kpi/targets/achievement",
        [
            {"key": "city", "label": "城市"},
            {"key": "metric_date", "label": "日期"},
            {"key": "score", "label": "得分"},
            {"key": "target", "label": "目标"},
            {"key": "achievement", "label": "达成率", "format": "pct"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/kpi/targets/sync",
    )


@app.route("/kpi/non_catering")
@login_required
def page_kpi_non_catering():
    return _data_page(
        "非餐 KPI 考核",
        "/api/kpi/non_catering/achievement",
        [
            {"key": "city", "label": "城市"},
            {"key": "metric_date", "label": "日期"},
            {"key": "score", "label": "得分"},
            {"key": "target", "label": "目标"},
            {"key": "achievement", "label": "达成率", "format": "pct"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/kpi/non_catering/sync",
    )


@app.route("/kpi/warning")
@login_required
def page_kpi_warning():
    return _data_page(
        "城市警告",
        "/api/city_warning",
        [
            {"key": "city", "label": "城市"},
            {"key": "warn_date", "label": "日期"},
            {"key": "level", "label": "等级"},
            {"key": "content", "label": "内容"},
            {"key": "updated_at", "label": "更新时间"},
        ],
    )


@app.route("/kpi/delivery_fee")
@login_required
def page_delivery_fee():
    return render_template(
        "powerbi_subsidy.html",
        title="代补看板",
        api_endpoint="/api/kpi/powerbi_subsidy",
        sync_endpoint="/api/kpi/delivery_fee/sync",
    )


@app.route("/kpi/dashboard")
@login_required
def page_dashboard():
    return _data_page(
        "绩效看板",
        "/api/dashboard/metrics",
        [
            {"key": "city", "label": "城市"},
            {"key": "metric_date", "label": "日期"},
            {"key": "metric_key", "label": "指标"},
            {"key": "metric_value", "label": "数值"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/dashboard/sync",
    )


@app.route("/warning/catering")
@login_required
def page_warning_catering():
    return _data_page(
        "餐饮预警",
        "/api/catering_warning",
        [
            {"key": "city", "label": "城市"},
            {"key": "warn_date", "label": "日期"},
            {"key": "content", "label": "内容"},
            {"key": "updated_at", "label": "更新时间"},
        ],
    )


@app.route("/evaluation")
@login_required
def page_evaluation():
    return _data_page(
        "合作商评价体系",
        "/api/evaluation",
        [
            {"key": "city", "label": "城市"},
            {"key": "eval_date", "label": "日期"},
            {"key": "partner_name", "label": "合作商"},
            {"key": "score", "label": "得分"},
            {"key": "rank_no", "label": "排名"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/evaluation/sync",
    )


@app.route("/evaluation/xinshang")
def page_xinshang_dashboard():
    """川藏一区新商能力评价看板（免登录，可供外发域名访问）。"""
    return send_from_directory(
        BASE_DIR / "static" / "dashboards",
        "cz1-xinshang-pingjia.html",
    )


@app.route("/visit_check")
@login_required
def page_visit_check():
    return render_template(
        "visit_check.html",
        title="拜访检核",
        api_endpoint="/api/visit_check",
    )


@app.route("/todo_achievement")
@login_required
def page_todo():
    return _data_page(
        "TODO 达成",
        "/api/todo_achievement",
        [
            {"key": "city", "label": "城市"},
            {"key": "todo_date", "label": "日期"},
            {"key": "todo_name", "label": "任务"},
            {"key": "status", "label": "状态"},
            {"key": "progress", "label": "进度", "format": "pct"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/todo_achievement/sync",
    )


@app.route("/notice")
@login_required
def page_notice():
    return _data_page(
        "通知函",
        "/api/notices/meituan",
        [
            {"key": "title", "label": "标题"},
            {"key": "published_at", "label": "发布时间"},
            {"key": "content", "label": "摘要"},
            {"key": "updated_at", "label": "更新时间"},
        ],
        "/api/notices/meituan/sync",
    )


@app.route("/business")
@login_required
def page_business():
    return _data_page(
        "经营管理",
        "/api/business",
        [
            {"key": "city", "label": "城市"},
            {"key": "biz_date", "label": "日期"},
            {"key": "metric_key", "label": "指标"},
            {"key": "metric_value", "label": "数值"},
            {"key": "updated_at", "label": "更新时间"},
        ],
    )


@app.route("/team")
@login_required
def page_team():
    return _data_page(
        "团队管理",
        "/api/team",
        [
            {"key": "city", "label": "城市"},
            {"key": "member_name", "label": "成员"},
            {"key": "role", "label": "岗位"},
            {"key": "metric_date", "label": "日期"},
            {"key": "metric_key", "label": "指标"},
            {"key": "metric_value", "label": "数值"},
            {"key": "updated_at", "label": "更新时间"},
        ],
    )

# ---------- APIs ----------


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "region": REGION_NAME, "cities": CITIES})


@app.route("/api/kpi/targets/achievement")
@login_required
def api_catering_achievement():
    rows = db.query_all(
        """SELECT city, metric_date, score, target, achievement, updated_at
           FROM catering_daily_scores
           ORDER BY metric_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/kpi/non_catering/achievement")
@login_required
def api_non_catering_achievement():
    rows = db.query_all(
        """SELECT city, metric_date, score, target, achievement, updated_at
           FROM non_catering_daily_scores
           ORDER BY metric_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


POWERBI_SECTION_ORDER = ("餐饮", "非餐", "餐饮KA", "餐饮城商")
POWERBI_SORT_METRIC = "代理商补贴金额"


def _parse_powerbi_number(raw: str | None) -> float:
    if not raw:
        return 0.0
    s = str(raw).replace(",", "").replace("其他条件格式", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def _sort_powerbi_detail_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda x: _parse_powerbi_number(x.get("cells", {}).get(POWERBI_SORT_METRIC)),
        reverse=True,
    )


def _build_powerbi_subsidy_payload(
    city: str | None = None,
    snapshot_date: str | None = None,
    area: str | None = None,
) -> dict:
    latest = db.query_one("SELECT MAX(snapshot_date) AS d FROM powerbi_delivery_rows")
    if not snapshot_date:
        snapshot_date = latest["d"] if latest and latest.get("d") else None
    if not snapshot_date:
        return {
            "ok": True,
            "meta": {"snapshot_date": None, "city": city, "area": area},
            "sections": [],
            "filters": {"cities": [], "dates": [], "areas": []},
        }

    params: list[str] = [snapshot_date]
    where = "snapshot_date = ?"
    if area:
        where += " AND area = ?"
        params.append(area)
    if city:
        where += " AND city = ?"
        params.append(city)

    rows = db.query_all(
        f"""SELECT section, row_name, metric_key, metric_text, is_total, area, city
            FROM powerbi_delivery_rows
            WHERE {where}
            ORDER BY section, is_total, row_name, metric_key""",
        tuple(params),
    )

    filters = db.query_all(
        """SELECT DISTINCT snapshot_date, city, area FROM powerbi_delivery_rows
           ORDER BY snapshot_date DESC, area, city"""
    )
    filter_dates = sorted({r["snapshot_date"] for r in filters}, reverse=True)
    raw_cities = {r["city"] for r in filters if r.get("city")}
    filter_cities = [c for c in CITIES if c in raw_cities] + sorted(raw_cities - set(CITIES))
    filter_areas = sorted({r["area"] for r in filters if r.get("area")})
    if "川藏一区" in filter_areas:
        filter_areas = ["川藏一区", *[a for a in filter_areas if a != "川藏一区"]]

    meta_city = city or (rows[0]["city"] if rows else None)
    meta_area = area or (rows[0]["area"] if rows else None)

    grouped: dict[str, dict] = {}
    for r in rows:
        sec = r["section"]
        bucket = grouped.setdefault(sec, {"headers": [], "rows": {}})
        metric_key = r["metric_key"]
        if metric_key and metric_key not in bucket["headers"] and metric_key != "行选择":
            bucket["headers"].append(metric_key)
        row_key = (r["row_name"], int(r["is_total"] or 0))
        row_obj = bucket["rows"].setdefault(
            row_key,
            {"row_name": r["row_name"], "is_total": bool(r["is_total"]), "cells": {}},
        )
        row_obj["cells"]["活动大类"] = r["row_name"]
        row_obj["cells"][metric_key] = r["metric_text"]

    sections = []
    for sec in POWERBI_SECTION_ORDER:
        headers = grouped.get(sec, {"headers": [], "rows": {}})["headers"]
        if "活动大类" not in headers:
            headers = ["活动大类", *headers]
        else:
            headers = ["活动大类", *[h for h in headers if h != "活动大类"]]
        detail_rows = []
        total_rows = []
        for item in grouped.get(sec, {"rows": {}})["rows"].values():
            (total_rows if item["is_total"] else detail_rows).append(item)
        detail_rows = _sort_powerbi_detail_rows(detail_rows)
        sections.append(
            {
                "name": sec,
                "headers": headers or ["活动大类", "代理商补贴金额"],
                "rows": detail_rows + total_rows,
            }
        )

    return {
        "ok": True,
        "meta": {
            "snapshot_date": snapshot_date,
            "city": meta_city,
            "area": meta_area,
        },
        "sections": sections,
        "filters": {"cities": filter_cities, "dates": filter_dates, "areas": filter_areas},
    }


@app.route("/api/kpi/delivery_fee")
@login_required
def api_delivery_fee():
    daily = db.query_all(
        """SELECT city, metric_date, fee_amount, order_count, updated_at
           FROM delivery_fee_daily ORDER BY metric_date DESC, city"""
    )
    monthly = db.query_all(
        """SELECT city, month, fee_amount, updated_at
           FROM delivery_fee_monthly ORDER BY month DESC, city"""
    )
    return jsonify({"ok": True, "daily": daily, "monthly": monthly, "cities": CITIES})


@app.route("/api/kpi/powerbi_subsidy")
@login_required
def api_powerbi_subsidy():
    city = (request.args.get("city") or "").strip() or None
    area = (request.args.get("area") or "").strip() or None
    snapshot_date = (request.args.get("date") or "").strip() or None
    return jsonify(_build_powerbi_subsidy_payload(city=city, snapshot_date=snapshot_date, area=area))


@app.route("/api/dashboard/metrics")
@login_required
def api_dashboard():
    rows = db.query_all(
        """SELECT city, metric_date, metric_key, metric_value, updated_at
           FROM dashboard_metrics ORDER BY metric_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/evaluation")
@login_required
def api_evaluation():
    rows = db.query_all(
        """SELECT city, eval_date, partner_name, score, rank_no, updated_at
           FROM management_evaluation
           ORDER BY eval_date DESC, rank_no ASC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/todo_achievement")
@login_required
def api_todo():
    rows = db.query_all(
        """SELECT city, todo_date, todo_name, status, progress, updated_at
           FROM todo_achievements ORDER BY todo_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/notices/meituan")
@login_required
def api_notices():
    rows = db.query_all(
        """SELECT notice_id, title, published_at, content, source_url, updated_at
           FROM meituan_notices ORDER BY published_at DESC, id DESC LIMIT 100"""
    )
    return jsonify({"ok": True, "data": rows})


@app.route("/api/business")
@login_required
def api_business():
    rows = db.query_all(
        """SELECT city, biz_date, metric_key, metric_value, updated_at
           FROM business_data ORDER BY biz_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/team")
@login_required
def api_team():
    rows = db.query_all(
        """SELECT city, member_name, role, metric_date, metric_key, metric_value, updated_at
           FROM team_data ORDER BY city, member_name"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/city_warning")
@login_required
def api_city_warning():
    rows = db.query_all(
        """SELECT city, warn_date, level, content, updated_at
           FROM city_warning ORDER BY warn_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/catering_warning")
@login_required
def api_catering_warning():
    rows = db.query_all(
        """SELECT city, warn_date, content, updated_at
           FROM catering_warning ORDER BY warn_date DESC, city"""
    )
    return jsonify({"ok": True, "data": rows, "cities": CITIES})


@app.route("/api/visit_check")
@login_required
def api_visit_check():
    import json as _json

    check_date = (request.args.get("date") or "").strip() or None
    latest = db.query_one("SELECT MAX(check_date) AS d FROM visit_check_daily")
    if not check_date:
        check_date = latest["d"] if latest and latest.get("d") else None
    if not check_date:
        return jsonify(
            {
                "ok": True,
                "meta": {"check_date": None, "city_total": 0, "city_with_data": 0},
                "region": {},
                "cities": [],
                "filters": {"dates": []},
            }
        )

    rows = db.query_all(
        """SELECT check_date, city, has_data, status, bd_total, bd_compliant, bd_rate,
                  visit_total, visit_compliant, visit_rate, coop_count, noncoop_count, detail_json
           FROM visit_check_daily WHERE check_date=? ORDER BY city""",
        (check_date,),
    )
    # prefer platform city order
    order = {c: i for i, c in enumerate(CITIES)}
    rows = sorted(rows, key=lambda r: order.get(r["city"], 99))

    cities = []
    for r in rows:
        detail = {}
        try:
            detail = _json.loads(r["detail_json"] or "{}")
        except Exception:
            detail = {}
        cities.append(
            {
                "city": r["city"],
                "has_data": bool(r["has_data"]),
                "status": r["status"],
                "bd_total": r["bd_total"],
                "bd_compliant": r["bd_compliant"],
                "bd_rate": r["bd_rate"],
                "visit_total": r["visit_total"],
                "visit_compliant": r["visit_compliant"],
                "visit_rate": r["visit_rate"],
                "coop_count": r["coop_count"],
                "noncoop_count": r["noncoop_count"],
                "bds": detail.get("bds") or [],
                "issues": detail.get("issues") or [],
            }
        )

    with_data = [c for c in cities if c["has_data"]]
    region = {
        "bd_total": sum(c["bd_total"] or 0 for c in with_data),
        "bd_compliant": sum(c["bd_compliant"] or 0 for c in with_data),
        "visit_total": sum(c["visit_total"] or 0 for c in with_data),
        "visit_compliant": sum(c["visit_compliant"] or 0 for c in with_data),
        "city_no_data": [c["city"] for c in cities if not c["has_data"]],
        "city_total": len(cities),
        "city_with_data": len(with_data),
    }
    region["bd_rate"] = (
        round(region["bd_compliant"] / region["bd_total"] * 100, 1) if region["bd_total"] else 0
    )
    region["visit_rate"] = (
        round(region["visit_compliant"] / region["visit_total"] * 100, 1)
        if region["visit_total"]
        else 0
    )

    dates = [
        x["check_date"]
        for x in db.query_all("SELECT DISTINCT check_date FROM visit_check_daily ORDER BY check_date DESC")
    ]
    return jsonify(
        {
            "ok": True,
            "meta": {
                "check_date": check_date,
                "city_total": region["city_total"],
                "city_with_data": region["city_with_data"],
            },
            "region": region,
            "cities": cities,
            "filters": {"dates": dates},
        }
    )


@app.route("/api/visit_check/import", methods=["POST"])
def api_visit_check_import():
    """Cloud Agent 推送后台导出检核结果；可用 X-CZ-Token（站密码）或已登录会话。"""
    from io import BytesIO

    token = (request.headers.get("X-CZ-Token") or request.form.get("token") or "").strip()
    if token != SITE_PASSWORD and not session.get("authenticated"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    try:
        from scrapers.import_visit_check import import_payload
        from scrapers.visit_admin_excel import excel_to_payload

        payload = None
        if request.files.get("file"):
            raw = request.files["file"].read()
            payload = excel_to_payload(BytesIO(raw))
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            if body.get("cities"):
                payload = body
            elif body.get("xlsx_base64"):
                import base64

                payload = excel_to_payload(BytesIO(base64.b64decode(body["xlsx_base64"])))
        if not payload:
            return jsonify({"ok": False, "error": "需要 JSON payload（含 cities）或 file/xlsx_base64"}), 400

        out = import_payload(payload)
        return jsonify(
            {
                "ok": True,
                "check_date": out["check_date"],
                "rows": out["rows"],
                "region": out["region"],
                "cities": [
                    {
                        "city": c["city"],
                        "status": c["status"],
                        "bd_compliant": c["bd_compliant"],
                        "bd_total": c["bd_total"],
                        "visit_compliant": c["visit_compliant"],
                        "visit_total": c["visit_total"],
                    }
                    for c in out["cities"]
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001
        db.log_sync("visit_check_import", "fail", str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


def _run_scraper(script_name: str) -> dict:
    script = SCRAPERS_DIR / script_name
    if not script.exists():
        return {"ok": False, "error": f"脚本不存在: {script_name}"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        db.log_sync(script_name, "ok" if ok else "fail", (proc.stdout or proc.stderr)[-2000:])
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    except Exception as exc:  # noqa: BLE001
        db.log_sync(script_name, "fail", str(exc))
        return {"ok": False, "error": str(exc)}


@app.route("/api/evaluation/sync", methods=["POST"])
@login_required
def sync_evaluation():
    return jsonify(_run_scraper("scrape_evaluation_cdp.py"))


@app.route("/api/todo_achievement/sync", methods=["POST"])
@login_required
def sync_todo():
    return jsonify(_run_scraper("scrape_todo_achievement_cdp.py"))


@app.route("/api/notices/meituan/sync", methods=["POST"])
@login_required
def sync_notices():
    return jsonify(_run_scraper("scrape_meituan_cdp.py"))


@app.route("/api/kpi/delivery_fee/sync", methods=["POST"])
@login_required
def sync_delivery_fee():
    return jsonify(_run_scraper("scrape_delivery_fee_daily_cdp.py"))


@app.route("/api/dashboard/sync", methods=["POST"])
@login_required
def sync_dashboard():
    return jsonify(_run_scraper("scrape_dashboard_cdp.py"))


@app.route("/api/kpi/targets/sync", methods=["POST"])
@login_required
def sync_catering():
    return jsonify(_run_scraper("sync_catering_scores.py"))


@app.route("/api/kpi/non_catering/sync", methods=["POST"])
@login_required
def sync_non_catering():
    return jsonify(_run_scraper("sync_non_catering_scores.py"))


def create_app():
    db.init_db()
    db.seed_demo_if_empty()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=PORT, debug=True)
