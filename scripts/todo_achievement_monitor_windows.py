#!/usr/bin/env python3
"""Windows 本机定时：川藏一区 Todo 达成监控（API拉取 + 表格图片 + 企微推送）。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

BASE_URL = "http://www.chuxin.city"
ACCOUNT = "qiaoxianhai"
PASSWORD = "123"
REGION = "川藏一区"
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb"
TZ = ZoneInfo("Asia/Shanghai")

COLUMNS = [
    "考核开始",
    "考核结束",
    "合作城市",
    "业务类型",
    "指标名称",
    "业务目标",
    "已完成",
    "完成进度",
    "更新日期",
]


def _http_json(method: str, url: str, *, headers: Optional[dict] = None, body: Optional[dict] = None) -> dict:
    data = None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login(base_url: str, account: str, password: str) -> str:
    payload = _http_json(
        "POST",
        f"{base_url}/api/auth:signIn",
        body={"account": account, "password": password},
    )
    token = (payload.get("data") or {}).get("token")
    if not token:
        raise RuntimeError(f"登录失败，未拿到 token: {payload}")
    return token


def fetch_all_todos(base_url: str, token: str, region: str, page_size: int = 200) -> list[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Authenticator": "basic",
        "X-Data-Source": "rds-yw",
        "X-Role": "__union__",
        "X-Locale": "zh-CN",
        "X-Timezone": "+08:00",
    }
    filt = urllib.parse.quote(json.dumps({"区域": {"$eq": region}}, ensure_ascii=False))
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        url = f"{base_url}/api/v_zt_ywtodo:list?pageSize={page_size}&page={page}&filter={filt}"
        payload = _http_json("GET", url, headers=headers)
        chunk = payload.get("data") or []
        if not isinstance(chunk, list):
            raise RuntimeError(f"列表返回异常: {type(chunk)}")
        rows.extend(chunk)
        meta = payload.get("meta") or {}
        total_page = int(meta.get("totalPage") or 1)
        if page >= total_page:
            break
        page += 1
    return rows


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return None
    text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=TZ)
    except ValueError:
        return None


def _parse_progress(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def filter_current_month(rows: list[dict[str, Any]], now: Optional[datetime] = None) -> list[dict[str, Any]]:
    now = now or datetime.now(TZ)
    out = []
    for row in rows:
        end = _parse_date(row.get("考核结束"))
        if end and end.year == now.year and end.month == now.month:
            out.append(row)
    # 稳定排序：考核结束升序，再按城市/指标
    out.sort(key=lambda r: (str(r.get("考核结束") or ""), str(r.get("合作城市") or ""), str(r.get("指标名称") or "")))
    return out


def count_unmet(rows: list[dict[str, Any]]) -> int:
    n = 0
    for row in rows:
        progress = _parse_progress(row.get("完成进度"))
        if progress is not None and progress < 1:
            n += 1
    return n


def max_update_date(rows: list[dict[str, Any]], fallback: datetime) -> str:
    dates = []
    for row in rows:
        d = _parse_date(row.get("更新日期"))
        if d:
            dates.append(d.date())
    if dates:
        return max(dates).isoformat()
    return fallback.astimezone(TZ).date().isoformat()


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _cell_text(row: dict[str, Any], col: str) -> str:
    val = row.get(col)
    if val is None:
        return ""
    if col == "完成进度":
        progress = _parse_progress(val)
        if progress is None:
            return str(val)
        if abs(progress - round(progress)) < 1e-9:
            return str(int(round(progress)))
        return f"{progress:.2f}"
    return str(val)


def render_table_png(rows: list[dict[str, Any]], output: Path) -> Path:
    font = _load_font(16)
    header_font = _load_font(16)
    padding_x = 10
    padding_y = 8
    min_col_widths = {
        "考核开始": 100,
        "考核结束": 100,
        "合作城市": 80,
        "业务类型": 90,
        "指标名称": 280,
        "业务目标": 90,
        "已完成": 80,
        "完成进度": 80,
        "更新日期": 100,
    }

    # 测算列宽
    col_widths: list[int] = []
    dummy = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(dummy)
    for col in COLUMNS:
        width = max(min_col_widths.get(col, 80), int(draw.textlength(col, font=header_font)) + padding_x * 2)
        for row in rows:
            text = _cell_text(row, col)
            width = max(width, int(draw.textlength(text, font=font)) + padding_x * 2)
        # 指标名称过长时限宽并依赖截断观感（仍完整绘制，允许较宽）
        if col == "指标名称":
            width = min(width, 420)
        col_widths.append(width)

    row_height = 34
    header_height = 38
    table_w = sum(col_widths) + 1
    table_h = header_height + row_height * max(len(rows), 1) + 1
    img = Image.new("RGB", (table_w, table_h), "white")
    draw = ImageDraw.Draw(img)

    # header
    x = 0
    for idx, col in enumerate(COLUMNS):
        w = col_widths[idx]
        draw.rectangle([x, 0, x + w, header_height], fill="#FFE566", outline="#333333")
        tw = draw.textlength(col, font=header_font)
        draw.text((x + (w - tw) / 2, (header_height - 18) / 2), col, fill="#000000", font=header_font)
        x += w

    if not rows:
        draw.rectangle([0, header_height, table_w, table_h], outline="#333333")
        draw.text((12, header_height + 8), "本月暂无 Todo 数据", fill="#333333", font=font)
    else:
        for r_i, row in enumerate(rows):
            y = header_height + r_i * row_height
            x = 0
            progress = _parse_progress(row.get("完成进度"))
            for c_i, col in enumerate(COLUMNS):
                w = col_widths[c_i]
                fill = "#FFFFFF"
                if col == "完成进度" and progress is not None and progress < 1:
                    fill = "#FFC7CE"  # 浅红
                draw.rectangle([x, y, x + w, y + row_height], fill=fill, outline="#666666")
                text = _cell_text(row, col)
                # 过长截断显示
                max_chars = max(4, int(w / 8))
                if len(text) > max_chars:
                    text = text[: max_chars - 1] + "…"
                tw = draw.textlength(text, font=font)
                draw.text((x + (w - tw) / 2, y + (row_height - 18) / 2), text, fill="#111111", font=font)
                x += w

    # 控制体积
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG", optimize=True)
    if output.stat().st_size > 2 * 1024 * 1024:
        # 等比缩小
        scale = 0.85
        while output.stat().st_size > 2 * 1024 * 1024 and scale > 0.4:
            new_size = (max(100, int(img.width * scale)), max(80, int(img.height * scale)))
            resized = img.resize(new_size, Image.Resampling.LANCZOS)
            resized.save(output, format="PNG", optimize=True)
            scale -= 0.1
            img = resized
    return output


def build_text(cutoff: str, unmet: int) -> str:
    if unmet > 0:
        return f"截止{cutoff}，川藏一区本月有{unmet}项todo未达成"
    return f"截止{cutoff}，川藏一区本月todo均达成"


def push_text(webhook: str, content: str) -> dict:
    body = _http_json("POST", webhook, body={"msgtype": "text", "text": {"content": content}})
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"text 推送失败: {body}")
    return body


def push_image(webhook: str, png_path: Path) -> dict:
    raw = png_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    md5 = hashlib.md5(raw).hexdigest()
    body = _http_json(
        "POST",
        webhook,
        body={"msgtype": "image", "image": {"base64": b64, "md5": md5}},
    )
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"image 推送失败: {body}")
    return body


def safe_cleanup(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    for child in path.glob("*"):
                        if child.is_file():
                            child.unlink(missing_ok=True)
                    path.rmdir()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="川藏一区 Todo 达成监控（Windows 定时）")
    parser.add_argument("--base-url", default=os.getenv("TODO_BASE_URL", BASE_URL))
    parser.add_argument("--account", default=os.getenv("TODO_ACCOUNT", ACCOUNT))
    parser.add_argument("--password", default=os.getenv("TODO_PASSWORD", PASSWORD))
    parser.add_argument("--webhook", default=os.getenv("TODO_WECOM_WEBHOOK", WEBHOOK))
    parser.add_argument(
        "--temp-dir",
        default=os.getenv("TODO_TEMP_DIR", r"C:\Windows\Temp\todo_monitor"),
        help="临时目录",
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成不推送")
    args = parser.parse_args()

    temp_dir = Path(args.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    png_path = temp_dir / f"todo_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.png"
    cleanup_paths = [png_path]

    try:
        now = datetime.now(TZ)
        token = login(args.base_url, args.account, args.password)
        all_rows = fetch_all_todos(args.base_url, token, REGION)
        month_rows = filter_current_month(all_rows, now=now)
        unmet = count_unmet(month_rows)
        cutoff = max_update_date(month_rows, now)
        text = build_text(cutoff, unmet)
        render_table_png(month_rows, png_path)

        summary = {
            "month_count": len(month_rows),
            "unmet_count": unmet,
            "text": text,
            "png": str(png_path),
            "png_size": png_path.stat().st_size,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if args.dry_run:
            print("dry-run: skip wecom push")
            return 0

        text_resp = push_text(args.webhook, text)
        image_resp = push_image(args.webhook, png_path)
        print(json.dumps({"text": text_resp, "image": image_resp}, ensure_ascii=False, indent=2))

        # errcode=0 后清理临时目录内文件
        cleanup_paths.extend(list(temp_dir.glob("*.png")))
        safe_cleanup(cleanup_paths)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
