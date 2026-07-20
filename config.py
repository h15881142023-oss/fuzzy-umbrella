"""川藏一区数据平台 — 全局配置"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

# 区域与城市（标准写法）
REGION_NAME = "川藏一区"
CITIES = ["仁寿县", "南溪", "叙永", "彭州市", "合江县"]

# 旧名 / 简称 → 标准名（导入与展示归一化）
CITY_ALIASES = {
    "仁寿": "仁寿县",
    "仁寿县": "仁寿县",
    "南溪": "南溪",
    "叙永": "叙永",
    "彭州": "彭州市",
    "彭州市": "彭州市",
    "合江": "合江县",
    "合江县": "合江县",
}


def normalize_city(name: str | None) -> str | None:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    return CITY_ALIASES.get(s, s)

# 对外域名（Cloudflare Tunnel 绑定）
PUBLIC_HOST = "1.chuanzangyiqu.top"
PUBLIC_ORIGIN = f"https://{PUBLIC_HOST}"

# Web
HOST = "0.0.0.0"
PORT = 5001
SECRET_KEY = os.environ.get("CZ_SECRET_KEY", "chuanzang-change-me-in-production")
# 共用站密码（可用环境变量覆盖）
SITE_PASSWORD = os.environ.get("CZ_SITE_PASSWORD", "chuanzang2026")

# 拜访检核：后台导出目录（Cloud Agent 工作区；禁止落到用户 Downloads）
VISIT_ADMIN_URL = os.environ.get(
    "CZ_VISIT_ADMIN_URL",
    "http://47.112.178.78:13000/admin/iefct5mpj1o/tab/47nekzoybbv",
)
VISIT_ADMIN_SIGNIN_URL = os.environ.get(
    "CZ_VISIT_ADMIN_SIGNIN_URL",
    "http://47.112.178.78:13000/signin",
)
VISIT_EXPORT_DIR = Path(
    os.environ.get("CZ_VISIT_EXPORT_DIR", str(BASE_DIR / "data" / "visit_exports"))
)

# Excel 监控目录
EXCEL_WATCH_ROOT = Path.home() / "Desktop" / "川藏一区数据更新"
EXCEL_FOLDERS = {
    "catering_kpi": EXCEL_WATCH_ROOT / "餐饮KPI",
    "non_catering_kpi": EXCEL_WATCH_ROOT / "非餐KPI",
    "team": EXCEL_WATCH_ROOT / "团队管理",
    "delivery_fee": EXCEL_WATCH_ROOT / "实付配送费",
    "business": EXCEL_WATCH_ROOT / "经营管理",
    "city_warning": EXCEL_WATCH_ROOT / "城市警告",
    "catering_warning": EXCEL_WATCH_ROOT / "餐饮预警",
}

# LR 独立系统（不走网站）
LR_DIR = BASE_DIR / "lr"
LR_ADMIN_URL = os.environ.get(
    "LR_ADMIN_URL",
    "http://47.112.178.78:13000/admin/g303bjgeytq",
)
LR_ADMIN_SIGNIN_URL = os.environ.get("LR_ADMIN_SIGNIN_URL", VISIT_ADMIN_SIGNIN_URL)
LR_SCRAPE_DIR = Path(os.environ.get("LR_SCRAPE_DIR", str(BASE_DIR / "data" / "lr_scrape")))
LR_TEMPLATE_DEFAULT = os.environ.get(
    "LR_TEMPLATE_PATH",
    "/Users/qxh/月度工作/2026年/26年1月工作/LR日报总表模版5.4版(川藏一区) .xlsx",
)

# Gunicorn
GUNICORN_BIND = f"{HOST}:{PORT}"
GUNICORN_PID = BASE_DIR / "gunicorn.pid"
GUNICORN_ACCESS_LOG = BASE_DIR / "access.log"
GUNICORN_ERROR_LOG = BASE_DIR / "error.log"
