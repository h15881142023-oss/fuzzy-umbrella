"""美团看板 CDP 抓取配置（可用环境变量或 meituan_endpoints.json 覆盖）。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import CITIES

SCRAPERS_DIR = Path(__file__).resolve().parent
ENDPOINTS_FILE = SCRAPERS_DIR / "meituan_endpoints.json"

CHROME_CDP_PORT = int(os.environ.get("MEITUAN_CDP_PORT", "9222"))
CHROME_PROFILE_DIR = os.environ.get(
    "MEITUAN_CHROME_PROFILE",
    str(Path.home() / ".chuanzang_chrome_meituan"),
)

TAB_URL_PATTERNS = [
    "ocrm.meituan.com",
    "igate.waimai.meituan.com",
    "waimai.meituan.com",
    "meituan.com",
    "sankuai.com",
]

NETWORK_KEYWORDS = {
    "dashboard": ["unitDashboard", "dashboard", "unit/dashboard", "performance", "kpiBoard"],
    "catering": ["catering", "foodKpi", "餐饮", "cater"],
    "non_catering": ["nonCatering", "non_catering", "非餐", "retail"],
    "todo": ["todo", "requirement", "task", "待办", "业务要求"],
    "notice": ["notice", "message", "通知", "announcement", "inbox"],
}

DEFAULT_ENDPOINTS: dict[str, Any] = {
    "pages": {
        "dashboard": "https://jx.ocrm.meituan.com/report/agentDashboard/unitDashboard.html",
        "todo": "https://jx.ocrm.meituan.com/report/agentDashboard/unitDashboard.html",
        "notice": "https://jx.ocrm.meituan.com/",
    },
    "api_fetch_urls": [],
    "network_keywords": NETWORK_KEYWORDS,
    "city_aliases": {
        "仁寿县": ["仁寿县", "仁寿"],
        "南溪": ["南溪"],
        "叙永": ["叙永"],
        "彭州市": ["彭州市", "彭州"],
        "合江县": ["合江县", "合江"],
    },
    "table_column_map": {
        "city": ["城市", "城 市", "city", "区域", "战区"],
        "score": ["得分", "考核得分", "score", "绩效得分", "KPI得分"],
        "target": ["目标", "目标值", "target"],
        "achievement": ["达成率", "完成率", "achievement", "达成"],
        "metric_key": ["指标", "metric", "项目"],
        "metric_value": ["数值", "值", "value", "完成值"],
        "todo_name": ["任务", "待办", "事项", "要求"],
        "status": ["状态", "status"],
        "progress": ["进度", "progress"],
        "title": ["标题", "title", "主题"],
        "content": ["内容", "摘要", "content"],
        "published_at": ["时间", "发布时间", "日期"],
    },
}


def load_endpoints() -> dict[str, Any]:
    data = json.loads(json.dumps(DEFAULT_ENDPOINTS))
    if ENDPOINTS_FILE.exists():
        user = json.loads(ENDPOINTS_FILE.read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(data.get(k), dict):
                data[k].update(v)
            else:
                data[k] = v
    for key in ("dashboard", "todo", "notice"):
        env_key = f"MEITUAN_{key.upper()}_URL"
        if os.environ.get(env_key):
            data.setdefault("pages", {})[key] = os.environ[env_key]
    urls = os.environ.get("MEITUAN_API_FETCH_URLS", "").strip()
    if urls:
        data["api_fetch_urls"] = [u.strip() for u in urls.split(",") if u.strip()]
    return data


def city_aliases(cfg: dict[str, Any]) -> dict[str, list[str]]:
    base = {c: [c] for c in CITIES}
    extra = cfg.get("city_aliases") or {}
    for city, aliases in extra.items():
        if city in base:
            base[city] = list(dict.fromkeys([city, *aliases]))
    return base
