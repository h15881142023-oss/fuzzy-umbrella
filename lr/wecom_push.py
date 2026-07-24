"""企业微信 webhook：只推图片 + Excel（无文案）。

企微机器人 image 消息每次只能 1 张图（且原图 <2MB），
多城看板会先竖向拼成一张再推送。
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import urllib.request
from pathlib import Path

# 企微 webhook 图片限制：编码前不超过 2MB
WECOM_IMAGE_MAX_BYTES = 2 * 1024 * 1024 - 32 * 1024


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


def stitch_pngs_vertical(
    pngs: list[Path],
    out_path: Path,
    *,
    gap: int = 16,
    bg: tuple[int, int, int] = (245, 245, 245),
    max_width: int = 1600,
) -> Path:
    """竖向拼接多图，并压缩到企微 2MB 以内；可能返回 .png 或 .jpg。"""
    from PIL import Image

    if not pngs:
        raise ValueError("没有可拼接的图片")

    images: list[Image.Image] = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        if im.width > max_width:
            ratio = max_width / im.width
            im = im.resize(
                (max_width, max(1, int(im.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        images.append(im)

    width = max(im.width for im in images)
    height = sum(im.height for im in images) + gap * max(len(images) - 1, 0)
    canvas = Image.new("RGB", (width, height), bg)
    y = 0
    for im in images:
        x = (width - im.width) // 2
        canvas.paste(im, (x, y))
        y += im.height + gap

    out_path.parent.mkdir(parents=True, exist_ok=True)

    png_path = out_path.with_suffix(".png")
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    if len(data) <= WECOM_IMAGE_MAX_BYTES:
        png_path.write_bytes(data)
        return png_path

    work = canvas
    for width_cap in (work.width, 1400, 1200, 1000, 800, 640):
        if work.width > width_cap:
            ratio = width_cap / work.width
            work = work.resize(
                (width_cap, max(1, int(work.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        for quality in (85, 75, 65, 55, 45, 35, 28):
            buf = io.BytesIO()
            work.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= WECOM_IMAGE_MAX_BYTES:
                jpg_path = out_path.with_suffix(".jpg")
                jpg_path.write_bytes(data)
                return jpg_path

    raise RuntimeError("拼图压缩后仍超过企微 2MB 限制")


def push_image(webhook: str, image_path: Path) -> dict:
    image = image_path.read_bytes()
    if len(image) > 2 * 1024 * 1024:
        raise RuntimeError(f"图片超过 2MB: {image_path} ({len(image)} bytes)")
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
        raise RuntimeError(f"图片推送失败: {image_path.name} -> {resp}")
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
    combined_out: Path | None = None,
) -> dict:
    """推送一张拼合看板图 + Excel；不发送 markdown 文案。"""
    del title
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

    if len(images) == 1:
        combined = images[0]
    else:
        out = combined_out or images[0].parent / "看板-单城_五城拼接.png"
        combined = stitch_pngs_vertical(images, out)

    img_resp = push_image(webhook, combined)
    file_resp = push_file(webhook, xlsx)
    return {
        "image": img_resp,
        "file": file_resp,
        "combined": str(combined),
        "source_count": len(images),
    }
