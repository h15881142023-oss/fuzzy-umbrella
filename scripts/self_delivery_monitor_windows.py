#!/usr/bin/env python3
"""Windows 本机定时：自配门店监控（看板下载 + pandas筛选 + 企微推送）。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BOARD_URL = "http://47.112.178.78:8100/#/de-link/zjygliyM?ticket=8GbVO1Vw"
BOARD_PASSWORD = "mtwm@888"
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb"

DELIVERY_ALLOWED = {"跑腿", "商家配送"}
BIZ_ALLOWED = {"城市商家", "全国KA", "区域KA"}


@dataclass
class MonitorResult:
    month_count: int
    recent_count: int
    recent_df: pd.DataFrame
    recent_file: Path
    markdown: str


def _pick_column(df: pd.DataFrame, candidates: list[str], fallback_index: int) -> str:
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        hit = lower_map.get(name.strip().lower())
        if hit is not None:
            return hit
    if fallback_index >= len(df.columns):
        raise IndexError(f"备用列索引越界: {fallback_index}, 当前列数={len(df.columns)}")
    return str(df.columns[fallback_index])


def _parse_date_series(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip()
    normalized = normalized.replace({"": None, "nan": None, "NaT": None})
    return pd.to_datetime(normalized, errors="coerce").dt.date


def _click_text(page, text: str, timeout_ms: int = 10000) -> None:
    locator = page.get_by_text(text, exact=False)
    locator.first.wait_for(timeout=timeout_ms)
    locator.first.click()


def _wait_table_ready(page, timeout_ms: int = 90000) -> None:
    page.get_by_text("商家ID", exact=False).first.wait_for(timeout=timeout_ms)
    page.get_by_text("商家名称", exact=False).first.wait_for(timeout=timeout_ms)
    page.wait_for_timeout(2000)


def _hover_table_area(page) -> None:
    """表格需先悬停，右侧才会出现下载工具栏。"""
    table_selectors = [
        "table tbody tr td",
        ".ant-table-tbody tr td",
        "[class*='table'] tbody tr td",
        "[class*='vtable']",
        "[class*='sheet']",
    ]
    for selector in table_selectors:
        cell = page.locator(selector).first
        try:
            cell.wait_for(state="visible", timeout=3000)
            cell.hover(force=True)
            page.wait_for_timeout(800)
            return
        except PlaywrightTimeoutError:
            continue

    viewport = page.viewport_size or {"width": 1280, "height": 720}
    page.mouse.move(viewport["width"] // 2, viewport["height"] // 2 + 80)
    page.wait_for_timeout(800)


def _click_table_download(page) -> None:
    """悬停表格后点击右侧下载图标，再选 Excel。"""
    table_roots = [
        page.locator("table").first,
        page.locator(".ant-table").first,
        page.locator("[class*='table-container']").first,
        page.locator("[class*='vtable']").first,
    ]

    download_selectors = [
        '[title="下载"]',
        '[title*="下载"]',
        '[aria-label="下载"]',
        '[aria-label*="下载"]',
        '[class*="download"]',
        'i[class*="download"]',
    ]

    last_error: Optional[Exception] = None
    for _ in range(4):
        _hover_table_area(page)
        clicked = False

        for selector in download_selectors:
            btn = page.locator(selector).filter(has_not=page.locator("[hidden]"))
            try:
                if btn.count() == 0:
                    continue
                target = btn.last
                target.wait_for(state="visible", timeout=1500)
                target.click(timeout=5000)
                clicked = True
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if not clicked:
            for root in table_roots:
                try:
                    box = root.bounding_box()
                    if not box:
                        continue
                    x = box["x"] + box["width"] - 18
                    y = box["y"] + 52
                    page.mouse.move(x, y)
                    page.wait_for_timeout(300)
                    page.mouse.click(x, y)
                    clicked = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

        if clicked:
            excel_item = page.get_by_text("Excel", exact=False).first
            excel_item.wait_for(state="visible", timeout=8000)
            excel_item.click()
            return

        page.wait_for_timeout(800)

    raise RuntimeError(f"未找到下载按钮（需先悬停表格区域）: {last_error}")


def _download_excel_impl(download_dir: Path, *, url: str, password: str, headless: bool) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.set_event_loop(asyncio.new_event_loop())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1600, "height": 900})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=120000)

        # 看板有时会弹密码输入框，无需登录则直接跳过。
        try:
            pwd_input = page.locator('input[type="password"]').first
            pwd_input.wait_for(timeout=5000)
            pwd_input.fill(password)
            confirm_btn = page.get_by_role("button", name="确定").first
            confirm_btn.click()
        except PlaywrightTimeoutError:
            pass

        page.get_by_text("每日指标看板", exact=False).first.wait_for(timeout=120000)
        _click_text(page, "商家明细-昨日", timeout_ms=30000)
        _wait_table_ready(page)

        with page.expect_download(timeout=120000) as download_info:
            _click_table_download(page)
        download = download_info.value
        suggest = download.suggested_filename or f"self_delivery_{int(time.time())}.xlsx"
        output = download_dir / suggest
        download.save_as(str(output))

        context.close()
        browser.close()
        return output


def download_excel(download_dir: Path, *, url: str, password: str, headless: bool) -> Path:
    """Windows 下用子进程隔离 Playwright，避免 event loop 冲突。"""
    if sys.platform != "win32":
        return _download_excel_impl(
            download_dir, url=url, password=password, headless=headless
        )

    marker = download_dir / ".download_result.json"
    if marker.exists():
        marker.unlink(missing_ok=True)

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--download-only",
        "--url",
        url,
        "--password",
        password,
        "--temp-dir",
        str(download_dir),
    ]
    if headless:
        cmd.append("--headless")

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or "浏览器下载子进程失败")

    if not marker.exists():
        raise RuntimeError("下载完成但未生成结果标记文件")

    payload = json.loads(marker.read_text(encoding="utf-8"))
    marker.unlink(missing_ok=True)
    return Path(payload["path"])


def build_filtered_result(raw_excel: Path, temp_dir: Path) -> MonitorResult:
    df = pd.read_excel(raw_excel, dtype=str)
    if df.empty:
        raise RuntimeError("下载的 Excel 为空，无法筛选")

    col_delivery = str(df.columns[2])  # C 列
    col_biz = str(df.columns[6])  # G 列
    col_online = str(df.columns[17])  # R 列

    month_df = df[df[col_delivery].isin(DELIVERY_ALLOWED) & df[col_biz].isin(BIZ_ALLOWED)].copy()
    month_df[col_online] = _parse_date_series(month_df[col_online])

    today = date.today()
    month_df = month_df[month_df[col_online].notna()].copy()
    month_df = month_df[
        (month_df[col_online].apply(lambda d: d.year) == today.year)
        & (month_df[col_online].apply(lambda d: d.month) == today.month)
    ].copy()
    month_count = len(month_df)

    start_day = today - timedelta(days=2)
    recent_df = month_df[(month_df[col_online] >= start_day) & (month_df[col_online] <= today)].copy()
    recent_count = len(recent_df)

    city_col = _pick_column(month_df, ["城市", "city"], fallback_index=1)
    store_col = _pick_column(month_df, ["门店", "门店名称", "商家名称", "store"], fallback_index=3)
    id_col = _pick_column(month_df, ["ID", "门店ID", "商家ID", "store_id"], fallback_index=0)

    pretty_df = recent_df[[city_col, store_col, id_col, col_delivery, col_biz, col_online]].copy()
    pretty_df.columns = ["城市", "门店", "ID", "配送类型", "商家类型", "上线时间"]
    pretty_df = pretty_df.sort_values(by=["上线时间", "城市", "门店"], ascending=[False, True, True])

    file_date = today.strftime("%Y%m%d")
    filtered_file = temp_dir / f"自配门店近3天_{file_date}.xlsx"
    pretty_df.to_excel(filtered_file, index=False)

    city_distribution = (
        pretty_df.groupby("城市").size().sort_values(ascending=False).to_dict()
        if recent_count > 0
        else {}
    )
    city_lines = "\n".join([f"> {k}：{v}" for k, v in city_distribution.items()]) or "> 无"
    detail_lines = "\n".join(
        [
            f"> {r.城市}｜{r.门店}｜{r.ID}｜{r.配送类型}｜{r.商家类型}｜{r.上线时间}"
            for r in pretty_df.itertuples(index=False)
        ]
    )
    if not detail_lines:
        detail_lines = "> 无"

    markdown = (
        f"## 📋 自配门店监控（{today.isoformat()}）\n"
        f"> 统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> 当月全量：{month_count}\n"
        f"> 近3天数量：{recent_count}\n\n"
        f"### 城市分布\n{city_lines}\n\n"
        f"### 门店明细（城市｜门店｜ID｜配送类型｜商家类型｜上线时间）\n{detail_lines}"
    )

    return MonitorResult(
        month_count=month_count,
        recent_count=recent_count,
        recent_df=pretty_df,
        recent_file=filtered_file,
        markdown=markdown,
    )


def _post_json(url: str, payload: dict) -> dict:
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"企微发送失败: {body}")
    return body


def _upload_file(webhook: str, path: Path) -> dict:
    key = parse_qs(urlparse(webhook).query).get("key", [None])[0]
    if not key:
        raise RuntimeError("Webhook 缺少 key 参数")
    upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file"
    with path.open("rb") as f:
        files = {
            "media": (
                path.name,
                f,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        resp = requests.post(upload_url, files=files, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"企微文件上传失败: {body}")
    return body


def push_wecom(webhook: str, result: MonitorResult) -> dict:
    if result.recent_count == 0:
        text = f"📋 自配门店监控（{date.today().isoformat()}）：近3日无自配门店上线"
        text_resp = _post_json(webhook, {"msgtype": "text", "text": {"content": text}})
        return {"text": text_resp}

    md_resp = _post_json(webhook, {"msgtype": "markdown", "markdown": {"content": result.markdown}})
    upload_resp = _upload_file(webhook, result.recent_file)
    file_resp = _post_json(
        webhook,
        {"msgtype": "file", "file": {"media_id": upload_resp["media_id"]}},
    )
    return {"markdown": md_resp, "upload": upload_resp, "file": file_resp}


def safe_unlink(path: Optional[Path]) -> None:
    if path and path.exists():
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="自配门店监控（Windows 本机定时）")
    parser.add_argument("--url", default=os.getenv("SELF_DELIVERY_BOARD_URL", BOARD_URL))
    parser.add_argument("--password", default=os.getenv("SELF_DELIVERY_BOARD_PASSWORD", BOARD_PASSWORD))
    parser.add_argument("--webhook", default=os.getenv("SELF_DELIVERY_WECOM_WEBHOOK", WEBHOOK))
    parser.add_argument(
        "--temp-dir",
        default=os.getenv("SELF_DELIVERY_TEMP_DIR", r"C:\Windows\Temp\zpei_monitor"),
        help="Windows 临时目录",
    )
    parser.add_argument("--headless", action="store_true", help="无头模式运行浏览器")
    parser.add_argument(
        "--download-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    temp_dir = Path(args.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    if args.download_only:
        try:
            downloaded = _download_excel_impl(
                temp_dir,
                url=args.url,
                password=args.password,
                headless=args.headless,
            )
            marker = temp_dir / ".download_result.json"
            marker.write_text(
                json.dumps({"path": str(downloaded)}, ensure_ascii=False),
                encoding="utf-8",
            )
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"执行失败: {exc}", file=sys.stderr)
            return 1

    downloaded_excel: Optional[Path] = None
    filtered_excel: Optional[Path] = None

    try:
        downloaded_excel = download_excel(
            temp_dir, url=args.url, password=args.password, headless=args.headless
        )
        result = build_filtered_result(downloaded_excel, temp_dir)
        filtered_excel = result.recent_file
        push_resp = push_wecom(args.webhook, result)
        print(json.dumps(push_resp, ensure_ascii=False, indent=2))

        # 仅在推送成功（errcode=0）后删除临时 Excel。
        safe_unlink(downloaded_excel)
        safe_unlink(filtered_excel)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
