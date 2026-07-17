"""Excel 拖放导入：监控桌面「川藏一区数据更新」文件夹。

期望列（可多列，至少包含 city；其余按模块映射）：
- 餐饮KPI / 非餐KPI: city, metric_date, score, target
- 实付配送费: city, metric_date, fee_amount, order_count
- 经营管理: city, biz_date, metric_key, metric_value
- 团队管理: city, member_name, role, metric_date, metric_key, metric_value
- 城市警告: city, warn_date, level, content
- 餐饮预警: city, warn_date, content
- 经营管理（评价）: 若含 partner_name / score 则写入 management_evaluation
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import db
from config import EXCEL_FOLDERS, EXCEL_WATCH_ROOT


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "城市": "city",
        "城 市": "city",
        "日期": "metric_date",
        "得分": "score",
        "目标": "target",
        "达成率": "achievement",
        "配送费": "fee_amount",
        "实付配送费": "fee_amount",
        "单量": "order_count",
        "指标": "metric_key",
        "数值": "metric_value",
        "成员": "member_name",
        "姓名": "member_name",
        "岗位": "role",
        "角色": "role",
        "等级": "level",
        "内容": "content",
        "告警": "content",
        "合作商": "partner_name",
        "排名": "rank_no",
        "业务日期": "biz_date",
        "月份": "month",
    }
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.rename(columns={k: v for k, v in mapping.items() if k in df.columns}, inplace=True)
    return df


def _read_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    return _normalize_columns(df)


def import_catering(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        if not city:
            continue
        date = str(r.get("metric_date") or _today())[:10]
        score = float(r["score"]) if pd.notna(r.get("score")) else None
        target = float(r["target"]) if pd.notna(r.get("target")) else None
        ach = None
        if score is not None and target:
            ach = score / target
        elif pd.notna(r.get("achievement")):
            ach = float(r["achievement"])
        rows.append((city, date, score, target, ach, None, ts))
    return db.upsert_many(
        """INSERT OR REPLACE INTO catering_daily_scores
           (city, metric_date, score, target, achievement, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def import_non_catering(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        if not city:
            continue
        date = str(r.get("metric_date") or _today())[:10]
        score = float(r["score"]) if pd.notna(r.get("score")) else None
        target = float(r["target"]) if pd.notna(r.get("target")) else None
        ach = (score / target) if score is not None and target else None
        rows.append((city, date, score, target, ach, None, ts))
    return db.upsert_many(
        """INSERT OR REPLACE INTO non_catering_daily_scores
           (city, metric_date, score, target, achievement, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def import_delivery(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        if not city:
            continue
        date = str(r.get("metric_date") or _today())[:10]
        fee = float(r["fee_amount"]) if pd.notna(r.get("fee_amount")) else None
        orders = float(r["order_count"]) if pd.notna(r.get("order_count")) else None
        rows.append((city, date, fee, orders, None, ts))
    return db.upsert_many(
        """INSERT OR REPLACE INTO delivery_fee_daily
           (city, metric_date, fee_amount, order_count, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )


def import_team(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        name = str(r.get("member_name", "")).strip()
        if not city or not name:
            continue
        rows.append(
            (
                city,
                name,
                str(r.get("role") or ""),
                str(r.get("metric_date") or _today())[:10],
                str(r.get("metric_key") or "出勤"),
                float(r["metric_value"]) if pd.notna(r.get("metric_value")) else None,
                None,
                ts,
            )
        )
    return db.upsert_many(
        """INSERT INTO team_data
           (city, member_name, role, metric_date, metric_key, metric_value, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def import_business(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    n = 0
    if "partner_name" in df.columns:
        rows = []
        for _, r in df.iterrows():
            city = str(r.get("city", "")).strip()
            partner = str(r.get("partner_name", "")).strip()
            if not city or not partner:
                continue
            rows.append(
                (
                    city,
                    str(r.get("metric_date") or r.get("biz_date") or _today())[:10],
                    partner,
                    float(r["score"]) if pd.notna(r.get("score")) else None,
                    int(r["rank_no"]) if pd.notna(r.get("rank_no")) else None,
                    None,
                    ts,
                )
            )
        n += db.upsert_many(
            """INSERT OR REPLACE INTO management_evaluation
               (city, eval_date, partner_name, score, rank_no, detail_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        key = str(r.get("metric_key", "")).strip()
        if not city or not key:
            continue
        rows.append(
            (
                city,
                str(r.get("biz_date") or r.get("metric_date") or _today())[:10],
                key,
                float(r["metric_value"]) if pd.notna(r.get("metric_value")) else None,
                None,
                ts,
            )
        )
    n += db.upsert_many(
        """INSERT OR REPLACE INTO business_data
           (city, biz_date, metric_key, metric_value, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )
    return n


def import_city_warning(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        if not city:
            continue
        rows.append(
            (
                city,
                str(r.get("warn_date") or r.get("metric_date") or _today())[:10],
                str(r.get("level") or "关注"),
                str(r.get("content") or ""),
                ts,
            )
        )
    return db.upsert_many(
        """INSERT INTO city_warning (city, warn_date, level, content, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )


def import_catering_warning(path: Path) -> int:
    df = _read_excel(path)
    ts = _now()
    rows = []
    for _, r in df.iterrows():
        city = str(r.get("city", "")).strip()
        if not city:
            continue
        rows.append(
            (
                city,
                str(r.get("warn_date") or r.get("metric_date") or _today())[:10],
                str(r.get("content") or ""),
                None,
                ts,
            )
        )
    return db.upsert_many(
        """INSERT INTO catering_warning (city, warn_date, content, extra_json, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )


IMPORTERS = {
    "catering_kpi": import_catering,
    "non_catering_kpi": import_non_catering,
    "delivery_fee": import_delivery,
    "team": import_team,
    "business": import_business,
    "city_warning": import_city_warning,
    "catering_warning": import_catering_warning,
}


def folder_key_for_path(path: Path) -> str | None:
    for key, folder in EXCEL_FOLDERS.items():
        try:
            path.resolve().relative_to(folder.resolve())
            return key
        except ValueError:
            continue
    return None


def import_file(path: Path) -> None:
    if path.name.startswith("~$") or path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
        return
    key = folder_key_for_path(path)
    if not key:
        return
    importer = IMPORTERS[key]
    # 等待文件写完
    time.sleep(0.8)
    n = importer(path)
    db.log_sync(f"excel:{key}", "ok", f"{path.name} -> {n} rows")
    print(f"[auto_sync] {key}: {path.name} -> {n} rows")


class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        import_file(Path(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return
        import_file(Path(event.src_path))


def ensure_folders() -> None:
    EXCEL_WATCH_ROOT.mkdir(parents=True, exist_ok=True)
    for folder in EXCEL_FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)


def scan_once() -> None:
    ensure_folders()
    db.init_db()
    for key, folder in EXCEL_FOLDERS.items():
        for path in sorted(folder.glob("*")):
            if path.is_file():
                try:
                    import_file(path)
                except Exception as exc:  # noqa: BLE001
                    db.log_sync(f"excel:{key}", "fail", f"{path.name}: {exc}")
                    print(f"[auto_sync] FAIL {path}: {exc}")


def watch_forever() -> None:
    ensure_folders()
    db.init_db()
    observer = Observer()
    handler = Handler()
    observer.schedule(handler, str(EXCEL_WATCH_ROOT), recursive=True)
    observer.start()
    print(f"[auto_sync] watching {EXCEL_WATCH_ROOT}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="扫描一次现有文件后退出")
    args = parser.parse_args()
    if args.once:
        scan_once()
    else:
        watch_forever()
