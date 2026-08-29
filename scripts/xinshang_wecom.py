"""新商评企微推送：与经营宝同一套 webhook（text）。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JYB_WECOM = (
    Path(os.environ.get("USERPROFILE", "") or os.environ.get("HOME", ""))
    / "Desktop"
    / "经营宝订单抓取"
    / "wecom_config.json"
)
LOCAL_WECOM = ROOT / "scripts" / "xinshang_wecom_config.json"
FALLBACK_WEBHOOK = (
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
    "?key=103699eb-8cd7-4af8-9fbe-46f01d315abb"
)
DEFAULT_PAGE = "https://1.chuanzangyiqu.top/evaluation/xinshang"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_wecom_config() -> dict:
    env = (os.environ.get("WECOM_WEBHOOK") or "").strip()
    if env:
        return {"webhook_url": env, "page_url": DEFAULT_PAGE, "source": "env"}

    for path in (JYB_WECOM, LOCAL_WECOM):
        if not path.is_file():
            continue
        data = _read_json(path)
        url = (data.get("webhook_url") or data.get("webhook") or "").strip()
        if url:
            return {
                "webhook_url": url,
                "page_url": (data.get("page_url") or DEFAULT_PAGE).strip(),
                "source": str(path),
            }
    return {"webhook_url": FALLBACK_WEBHOOK, "page_url": DEFAULT_PAGE, "source": "fallback"}


def send_text(content: str, webhook: str | None = None) -> dict:
    cfg = load_wecom_config()
    url = (webhook or cfg["webhook_url"]).strip()
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": content[:2048]}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"企微 HTTP {exc.code}: {raw}") from exc
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"企微失败: {body}")
    return body


def format_success(summary: dict) -> str:
    page = summary.get("page") or DEFAULT_PAGE
    lines = [
        "【新商评看板已更新】",
        f"数据日期：{summary.get('periodDate') or '—'}",
        f"上期：{summary.get('prevDate') or '—'}",
        f"同分群城市：{summary.get('universeCities') or '—'}",
        f"Power BI 月在线商家数：{summary.get('powerbi') or '—'}",
        f"外发页：{page}",
    ]
    note = summary.get("note")
    if note:
        lines.append(str(note))
    return "\n".join(lines)


def format_failure(err: str, step: str = "") -> str:
    lines = ["【新商评看板更新失败】"]
    if step:
        lines.append(f"步骤：{step}")
    lines.append(f"原因：{err[:1500]}")
    return "\n".join(lines)
