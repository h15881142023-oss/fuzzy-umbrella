"""从 CDN 补齐新商评同步脚本（本机 Web 启动时自动拉，不用复制 PowerShell）。"""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "477db4d"
BRANCH = "cursor/cz1-merchant-dashboard-74a9"

NEED = [
    "scripts/xinshang_daily_push.py",
    "scripts/xinshang_wecom.py",
    "scripts/xinshang_wecom_config.json",
    "scripts/xinshang_clock_windows.py",
    "scripts/sync_xinshang_from_chuxin.py",
    "scripts/sync_peer_compare_from_chuxin.py",
    "scripts/start_chrome_powerbi_windows.ps1",
    "scrapers/__init__.py",
    "scrapers/cdp_client.py",
    "scrapers/powerbi_wind_js.py",
    "scrapers/scrape_powerbi_wind_online.py",
]


def _urls(rel: str) -> list[str]:
    return [
        f"https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{SHA}/{rel}",
        f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{SHA}/{rel}",
        f"https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/{BRANCH}/{rel}",
        f"https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/{BRANCH}/{rel}",
    ]


def _download(rel: str) -> bytes | None:
    for url in _urls(rel):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cz1-xinshang"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if data and len(data) > 40:
                return data
        except Exception:
            continue
    return None


ALWAYS_REFRESH = {
    "scripts/xinshang_daily_push.py",
    "scripts/xinshang_wecom.py",
    "scripts/xinshang_wecom_config.json",
    "scrapers/cdp_client.py",
    "scrapers/scrape_powerbi_wind_online.py",
    "scripts/xinshang_clock_windows.py",
}


def ensure_tools(*, force: bool = False) -> dict:
    ok, missing = [], []
    for rel in NEED:
        dest = ROOT.joinpath(*rel.split("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        should = force or rel in ALWAYS_REFRESH or not dest.is_file() or dest.stat().st_size <= 40
        if dest.is_file() and not should:
            ok.append(rel)
            continue
        data = _download(rel)
        if not data:
            missing.append(rel)
            continue
        dest.write_bytes(data)
        ok.append(rel)
    return {"ok": ok, "missing": missing}


if __name__ == "__main__":
    print(ensure_tools())
