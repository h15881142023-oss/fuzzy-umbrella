"""新商评企微推送：同时发往多个 webhook。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_WECOM = ROOT / "scripts" / "xinshang_wecom_config.json"
DEFAULT_WEBHOOKS = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=8f0a0c3a-7636-4224-8ead-7b24fbb64157",
]
DEFAULT_PAGE = "https://1.chuanzangyiqu.top/evaluation/xinshang"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in urls:
        url = (raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def load_wecom_config() -> dict:
    urls: list[str] = []
    env = (os.environ.get("WECOM_WEBHOOK") or "").strip()
    if env:
        urls.extend(x.strip() for x in env.split(",") if x.strip())

    source = "fixed"
    if LOCAL_WECOM.is_file():
        data = _read_json(LOCAL_WECOM)
        one = (data.get("webhook_url") or data.get("webhook") or "").strip()
        many = data.get("webhook_urls") or data.get("webhooks") or []
        if one:
            urls.append(one)
        if isinstance(many, list):
            urls.extend(str(x).strip() for x in many)
        if one or many:
            source = str(LOCAL_WECOM)
        page = (data.get("page_url") or DEFAULT_PAGE).strip()
    else:
        page = DEFAULT_PAGE

    urls.extend(DEFAULT_WEBHOOKS)
    urls = _unique_urls(urls)
    return {
        "webhook_urls": urls,
        "webhook_url": urls[0] if urls else "",
        "page_url": page,
        "source": source,
    }


def _post_one(url: str, content: str) -> dict:
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


def send_text(content: str, webhook: str | None = None) -> dict:
    cfg = load_wecom_config()
    urls = list(cfg.get("webhook_urls") or [])
    extra = (webhook or "").strip()
    if extra:
        urls = _unique_urls([extra] + urls)
    if not urls:
        raise RuntimeError("没有可用的企微 webhook")
    results = []
    errors = []
    for url in urls:
        try:
            results.append({"url": url, "body": _post_one(url, content)})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
    if not results:
        raise RuntimeError("全部企微推送失败: " + " | ".join(errors))
    return {"ok": True, "sent": len(results), "failed": errors, "results": results}


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
