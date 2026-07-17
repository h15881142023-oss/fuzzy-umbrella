"""共用工具：CDP 抓取脚本可调用。真实选择器需按川藏一区看板登录态调试后补齐。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_status(name: str, payload: dict) -> None:
    out = BASE / "scrapers" / "_last_runs"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
