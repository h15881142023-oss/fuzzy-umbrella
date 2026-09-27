"""把仓库里的新商评 HTML 热覆盖到本机 Web 目录，无需手工跑 PowerShell。"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "cursor/cz1-merchant-dashboard-74a9"
HTML_RELS = (
    "static/dashboards/cz1-xinshang-pingjia.html",
    "docs/xinshang/index.html",
)
MIN_HTML_BYTES = 5000
_LAST_OK_AT = 0.0


def _urls(rel: str) -> list[str]:
    stamp = str(int(time.time()))
    return [
        f"https://ghproxy.net/https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/{BRANCH}/{rel}?t={stamp}",
        f"https://raw.githubusercontent.com/h15881142023-oss/fuzzy-umbrella/{BRANCH}/{rel}?t={stamp}",
        f"https://fastly.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{BRANCH}/{rel}?t={stamp}",
        f"https://gcore.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{BRANCH}/{rel}?t={stamp}",
        f"https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@{BRANCH}/{rel}?t={stamp}",
    ]


def _download(rel: str) -> bytes | None:
    for url in _urls(rel):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cz1-xinshang-hot-html"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if data and len(data) > MIN_HTML_BYTES and b"<!DOCTYPE html>" in data[:200]:
                return data
        except Exception:
            continue
    return None


def pull_once() -> dict:
    """立刻从 GitHub 分支拉最新看板 HTML，写到本机 static 与 docs。"""
    global _LAST_OK_AT
    ok, missing = [], []
    primary = None
    for rel in HTML_RELS:
        dest = ROOT.joinpath(*rel.split("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = _download(rel)
        if not data:
            missing.append(rel)
            continue
        dest.write_bytes(data)
        ok.append(rel)
        if primary is None:
            primary = data
    if primary and "docs/xinshang/index.html" in missing:
        dest = ROOT / "docs" / "xinshang" / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(primary)
        missing = [m for m in missing if m != "docs/xinshang/index.html"]
        ok.append("docs/xinshang/index.html")
    if ok and not missing:
        _LAST_OK_AT = time.time()
    return {"ok": ok, "missing": missing, "bytes": len(primary or b"")}


def ensure(*, min_interval_sec: float = 45, force: bool = False) -> dict:
    """访问外发页时调用：间隔内跳过，避免每次请求都打 GitHub。"""
    if not force and _LAST_OK_AT and (time.time() - _LAST_OK_AT) < min_interval_sec:
        return {"ok": list(HTML_RELS), "missing": [], "skipped": True}
    return pull_once()


if __name__ == "__main__":
    print(pull_once())
