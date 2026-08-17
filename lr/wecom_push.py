"""企业微信 webhook：只推图片 + Excel（无文案）。"""
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


def push_image(webhook: str, png: Path) -> dict:
    image = png.read_bytes()
    if len(image) > 2 * 1024 * 1024:
        raise RuntimeError(f"图片超过 2MB: {png} ({len(image)} bytes)")
    resp = post_json(
        webhook,
        {
            "msgtype": "image",
            "image": {
                "base64": base64.b64encode(image).decode("ascii"),
                "md5": hashlib.md5(image).hexdigest(),
            },
        },
    )
    if resp.get("errcode", 0) != 0:
        raise RuntimeError(f"图片推送失败: {png.name} -> {resp}")
    return resp


def push_text(webhook: str, content: str) -> dict:
    text = (content or "").strip()
    if not text:
        raise ValueError("empty text")
    resp = post_json(webhook, {"msgtype": "text", "text": {"content": text[:2048]}})
    if resp.get("errcode", 0) != 0:
        raise RuntimeError(f"文字推送失败: {resp}")
    return resp


def push_file(webhook: str, path: Path) -> dict:
    key = webhook.rsplit("key=", 1)[-1]
    file_id = upload_media(key, path, "file")
    resp = post_json(webhook, {"msgtype": "file", "file": {"media_id": file_id}})
    if resp.get("errcode", 0) != 0:
        raise RuntimeError(f"文件推送失败: {resp}")
    return resp


def push_lr_report(
    webhook: str,
    *,
    pngs: list[Path] | Path | None = None,
    xlsx: Path,
    title: str | None = None,  # 兼容旧参数，已忽略
    png: Path | None = None,  # 兼容旧单图参数
    combined_out: Path | None = None,  # 兼容旧参数，已忽略
) -> dict:
    """推送多张看板图（每张一条消息）+ Excel；不发送 markdown 文案。"""
    del title, combined_out
    images: list[Path] = []
    if png is not None:
        images.append(Path(png))
    if pngs is None:
        pass
    elif isinstance(pngs, (str, Path)):
        images.append(Path(pngs))
    else:
        images.extend(Path(p) for p in pngs)

    if not images:
        raise ValueError("至少需要一张 PNG")

    img_resps = [push_image(webhook, p) for p in images]
    file_resp = push_file(webhook, xlsx)
    return {"images": img_resps, "file": file_resp, "image_count": len(images)}


def main() -> int:
    import argparse
    import os
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import LR_WECOM_WEBHOOK  # noqa: E402

    parser = argparse.ArgumentParser(description="WeCom helpers")
    parser.add_argument("--text", help="send a text message to LR_WECOM_WEBHOOK")
    parser.add_argument("--webhook", default=os.environ.get("LR_WECOM_WEBHOOK", LR_WECOM_WEBHOOK))
    args = parser.parse_args()
    if args.text:
        resp = push_text(args.webhook, args.text)
        print(json.dumps({"ok": True, "wecom": resp}, ensure_ascii=False))
        return 0
    print("need --text", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
