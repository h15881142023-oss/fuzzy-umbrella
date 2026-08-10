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

# 业务后台默认登录（未单独说明账号密码时一律使用）
ADMIN_USER = os.environ.get("ADMIN_USER", "qiaoxianhai")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123")
ADMIN_SIGNIN_URL = os.environ.get(
    "ADMIN_SIGNIN_URL",
    "http://47.112.178.78:13000/signin",
)

# 企业微信机器人（Todo 周报等默认使用）
WECOM_WEBHOOK = os.environ.get(
    "WECOM_WEBHOOK",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb",
)

# 利润填写推送（LR 日报：填表 + 五城看板图 + Excel）
LR_WECOM_WEBHOOK = os.environ.get(
    "LR_WECOM_WEBHOOK",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb",
)

# 旧「利润数据源推送」已停用删除；保留变量以免外部 env 报错
LR_DATASOURCE_WECOM_WEBHOOK = os.environ.get(
    "LR_DATASOURCE_WECOM_WEBHOOK",
    "",
)

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
    "http://www.chuxin.city/v/admin/g303bjgeytq",
)
LR_ADMIN_SIGNIN_URL = os.environ.get(
    "LR_ADMIN_SIGNIN_URL",
    "http://www.chuxin.city/v/signin",
)
LR_SCRAPE_DIR = Path(os.environ.get("LR_SCRAPE_DIR", str(BASE_DIR / "data" / "lr_scrape")))
def _resolve_lr_template() -> str:
    """解析 LR 模板路径。

    优先英文别名 LR_DAILY_NEW.xlsx（避免 Windows PS1/GBK 中文路径乱码），
    其次中文名 LR日报_新.xlsx，再回退 templates 下非 5.4 的最新 xlsx。
    """
    env = os.environ.get("LR_TEMPLATE_PATH", "").strip()
    if env:
        return env
    tpl_dir = LR_DIR / "templates"
    ascii_alias = tpl_dir / "LR_DAILY_NEW.xlsx"
    if ascii_alias.exists():
        return str(ascii_alias)
    cn_new = tpl_dir / "LR日报_新.xlsx"
    if cn_new.exists():
        return str(cn_new)
    if tpl_dir.is_dir():
        cands = sorted(
            (
                p
                for p in tpl_dir.glob("*.xlsx")
                if "5.4" not in p.name and not p.name.startswith("~$")
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if cands:
            return str(cands[0])
    return str(cn_new)


LR_TEMPLATE_DEFAULT = _resolve_lr_template()

# KPI 待办进度（周一/周四 14:00 本机 launchd）
KPI_TODO_DIR = BASE_DIR / "kpi_todo"
KPI_TODO_ADMIN_URL = os.environ.get(
    "KPI_TODO_ADMIN_URL",
    "http://47.112.178.78:13000/admin/itgnwhaar7u",
)
KPI_TODO_SCRAPE_DIR = Path(
    os.environ.get("KPI_TODO_SCRAPE_DIR", str(BASE_DIR / "data" / "kpi_todo_scrape"))
)

# Gunicorn
GUNICORN_BIND = f"{HOST}:{PORT}"
GUNICORN_PID = BASE_DIR / "gunicorn.pid"
GUNICORN_ACCESS_LOG = BASE_DIR / "access.log"
GUNICORN_ERROR_LOG = BASE_DIR / "error.log"
