"""企业微信 webhook：推送 markdown + 图片。"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_media(webhook_key: str, path: Path, media_type: str = "image") -> str:
    upload_url = (
        f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media"
        f"?key={webhook_key}&type={media_type}"
    )
    mime = "image/png"
    proc = subprocess.run(
        ["curl", "-s", "-X", "POST", upload_url, "-F", f"media=@{path};type={mime}"],
        capture_output=True,
        text=True,
        check=False,
    )
    body = json.loads(proc.stdout or "{}")
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"上传失败: {body}")
    return body["media_id"]


def push_markdown(webhook: str, content: str) -> dict:
    resp = post_json(webhook, {"msgtype": "markdown", "markdown": {"content": content}})
    if resp.get("errcode", 0) != 0:
        raise RuntimeError(f"markdown 推送失败: {resp}")
    return resp


def push_image_base64(webhook: str, png: Path) -> dict:
    raw = png.read_bytes()
    payload = {
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(raw).decode("ascii"),
            "md5": hashlib.md5(raw).hexdigest(),
        },
    }
    resp = post_json(webhook, payload)
    if resp.get("errcode", 0) != 0:
        raise RuntimeError(f"图片推送失败: {resp}")
    return resp


def push_image(webhook: str, png: Path) -> dict:
    try:
        return push_image_base64(webhook, png)
    except RuntimeError:
        key = webhook.rsplit("key=", 1)[-1]
        media_id = upload_media(key, png, "image")
        resp = post_json(webhook, {"msgtype": "image", "image": {"media_id": media_id}})
        if resp.get("errcode", 0) != 0:
            raise RuntimeError(f"图片推送失败: {resp}")
        return resp


def push_report(webhook: str, *, title: str, png: Path) -> dict:
    md = push_markdown(webhook, title)
    img = push_image(webhook, png)
    return {"markdown": md, "image": img}
