"""SQLite 初始化与常用查询辅助"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Optional

from config import CITIES, DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catering_daily_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    score REAL,
    target REAL,
    achievement REAL,
    extra_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_date)
);

CREATE TABLE IF NOT EXISTS kpi_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    target REAL,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_key)
);

CREATE TABLE IF NOT EXISTS non_catering_daily_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    score REAL,
    target REAL,
    achievement REAL,
    extra_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_date)
);

CREATE TABLE IF NOT EXISTS non_catering_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    target REAL,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_key)
);

CREATE TABLE IF NOT EXISTS city_warning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    warn_date TEXT NOT NULL,
    level TEXT,
    content TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_fee_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    fee_amount REAL,
    order_count REAL,
    extra_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_date)
);

CREATE TABLE IF NOT EXISTS delivery_fee_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    month TEXT NOT NULL,
    fee_amount REAL,
    extra_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, month)
);

CREATE TABLE IF NOT EXISTS dashboard_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_value REAL,
    extra_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, metric_date, metric_key)
);

CREATE TABLE IF NOT EXISTS dashboard_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(snapshot_date)
);

CREATE TABLE IF NOT EXISTS catering_warning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    warn_date TEXT NOT NULL,
    content TEXT,
    extra_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS management_evaluation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    eval_date TEXT NOT NULL,
    partner_name TEXT,
    score REAL,
    rank_no INTEGER,
    detail_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, eval_date, partner_name)
);

CREATE TABLE IF NOT EXISTS todo_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    todo_date TEXT NOT NULL,
    todo_name TEXT NOT NULL,
    status TEXT,
    progress REAL,
    detail_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, todo_date, todo_name)
);

CREATE TABLE IF NOT EXISTS meituan_notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id TEXT,
    title TEXT,
    published_at TEXT,
    content TEXT,
    source_url TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(notice_id)
);

CREATE TABLE IF NOT EXISTS business_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    biz_date TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_value REAL,
    detail_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(city, biz_date, metric_key)
);

CREATE TABLE IF NOT EXISTS team_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    member_name TEXT NOT NULL,
    role TEXT,
    metric_date TEXT,
    metric_key TEXT,
    metric_value REAL,
    detail_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS powerbi_delivery_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    city TEXT,
    area TEXT,
    section TEXT NOT NULL,
    row_name TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_text TEXT,
    metric_value REAL,
    is_total INTEGER DEFAULT 0,
    detail_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(snapshot_date, city, section, row_name, metric_key)
);

CREATE TABLE IF NOT EXISTS visit_check_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_date TEXT NOT NULL,
    city TEXT NOT NULL,
    has_data INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    bd_total INTEGER DEFAULT 0,
    bd_compliant INTEGER DEFAULT 0,
    bd_rate REAL DEFAULT 0,
    visit_total INTEGER DEFAULT 0,
    visit_compliant INTEGER DEFAULT 0,
    visit_rate REAL DEFAULT 0,
    coop_count INTEGER DEFAULT 0,
    noncoop_count INTEGER DEFAULT 0,
    detail_json TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(check_date, city)
);
"""


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def log_sync(module: str, status: str, message: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO sync_log(module, status, message, created_at) VALUES (?, ?, ?, ?)",
            (module, status, message, now_str()),
        )


def upsert_many(sql: str, params_list: list[tuple]) -> int:
    if not params_list:
        return 0
    with connect() as conn:
        conn.executemany(sql, params_list)
        return len(params_list)


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(sql, params)
        return rows_to_dicts(cur.fetchall())


def query_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def seed_demo_if_empty() -> None:
    """首次启动写入少量演示数据，方便验收页面。"""
    existing = query_one("SELECT id FROM catering_daily_scores LIMIT 1")
    if existing:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    ts = now_str()
    catering = []
    non_catering = []
    delivery = []
    dashboard = []
    business = []
    evaluation = []
    todos = []
    for i, city in enumerate(CITIES):
        score = 80 + i * 3
        target = 100
        catering.append((city, today, score, target, score / target, None, ts))
        non_catering.append((city, today, score - 2, target, (score - 2) / target, None, ts))
        delivery.append((city, today, 12.5 + i, 1000 + i * 50, None, ts))
        dashboard.append((city, today, "gmv", 100000 + i * 8000, None, ts))
        business.append((city, today, "revenue", 50000 + i * 3000, None, ts))
        evaluation.append((city, today, f"{city}合作商", score + 5, i + 1, None, ts))
        todos.append((city, today, "本周重点任务", "进行中", 0.6, None, ts))

    upsert_many(
        """INSERT OR REPLACE INTO catering_daily_scores
           (city, metric_date, score, target, achievement, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        catering,
    )
    upsert_many(
        """INSERT OR REPLACE INTO non_catering_daily_scores
           (city, metric_date, score, target, achievement, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        non_catering,
    )
    upsert_many(
        """INSERT OR REPLACE INTO delivery_fee_daily
           (city, metric_date, fee_amount, order_count, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        delivery,
    )
    upsert_many(
        """INSERT OR REPLACE INTO dashboard_metrics
           (city, metric_date, metric_key, metric_value, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        dashboard,
    )
    upsert_many(
        """INSERT OR REPLACE INTO business_data
           (city, biz_date, metric_key, metric_value, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        business,
    )
    upsert_many(
        """INSERT OR REPLACE INTO management_evaluation
           (city, eval_date, partner_name, score, rank_no, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        evaluation,
    )
    upsert_many(
        """INSERT OR REPLACE INTO todo_achievements
           (city, todo_date, todo_name, status, progress, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        todos,
    )
    upsert_many(
        """INSERT OR IGNORE INTO meituan_notices
           (notice_id, title, published_at, content, source_url, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            ("demo-1", "【演示】川藏一区平台已就绪", today, "这是演示通知，真实抓取就绪后会替换。", "", ts),
        ],
    )
    for city in CITIES:
        upsert_many(
            """INSERT INTO team_data
               (city, member_name, role, metric_date, metric_key, metric_value, detail_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(city, f"{city}经理", "城市经理", today, "出勤", 1, None, ts)],
        )
        upsert_many(
            """INSERT INTO city_warning
               (city, warn_date, level, content, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(city, today, "关注", f"{city}暂无告警（演示）", ts)],
        )
    log_sync("seed", "ok", "写入演示数据")


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
