"""企业微信 webhook：推送图片 + Excel。"""
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


def upload_media(webhook_key: str, path: Path, media_type: str) -> str:
    upload_url = (
        f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media"
        f"?key={webhook_key}&type={media_type}"
    )
    if media_type == "file":
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
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


def image_message(path: Path) -> dict:
    content = path.read_bytes()
    return {
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(content).decode("ascii"),
            "md5": hashlib.md5(content).hexdigest(),
        },
    }


def push_lr_report(
    webhook: str,
    *,
    title: str,
    png: Path,
    xlsx: Path,
) -> dict:
    key = webhook.rsplit("key=", 1)[-1]

    md = post_json(
        webhook,
        {"msgtype": "markdown", "markdown": {"content": title}},
    )
    if md.get("errcode", 0) != 0:
        raise RuntimeError(f"markdown 推送失败: {md}")

    img_resp = post_json(webhook, image_message(png))
    if img_resp.get("errcode", 0) != 0:
        raise RuntimeError(f"图片推送失败: {img_resp}")

    file_id = upload_media(key, xlsx, "file")
    file_resp = post_json(webhook, {"msgtype": "file", "file": {"media_id": file_id}})
    if file_resp.get("errcode", 0) != 0:
        raise RuntimeError(f"文件推送失败: {file_resp}")

    return {"markdown": md, "image": img_resp, "file": file_resp}
