#!/usr/bin/env python3
"""Windows 本机定时：自配门店监控（看板下载 + pandas筛选 + 企微推送）。"""
from __future__ import annotations

import argparse
import json
import os
import re
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
from playwright.async_api import Frame, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

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


async def _iter_targets(page: Page) -> list[Page | Frame]:
    targets: list[Page | Frame] = [page]
    for frame in page.frames:
        if frame != page.main_frame:
            targets.append(frame)
    return targets


async def _click_text_in_any(page: Page, text: str, timeout_ms: int = 10000) -> None:
    deadline = time.time() + timeout_ms / 1000
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        for target in await _iter_targets(page):
            locator = target.get_by_text(text, exact=False)
            try:
                if await locator.count() == 0:
                    continue
                item = locator.first
                await item.scroll_into_view_if_needed(timeout=2000)
                await item.click(timeout=5000)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        await page.wait_for_timeout(500)
    raise RuntimeError(f"未找到可点击文本「{text}」: {last_error}")


async def _open_merchant_yesterday_tab(page: Page) -> None:
    tab_names = ["商家明细-昨日", "商明细-昨日", "商家明细"]
    last_error: Optional[Exception] = None
    for name in tab_names:
        try:
            await _click_text_in_any(page, name, timeout_ms=15000)
            await page.wait_for_timeout(2500)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"未能打开「商家明细-昨日」页签: {last_error}")


async def _target_has_table_data(target: Page | Frame) -> bool:
    checks = [
        target.locator("table tbody tr"),
        target.locator(".ant-table-tbody tr"),
        target.get_by_text(re.compile(r"共\s*\d+\s*条")),
        target.get_by_text("商家名称", exact=False),
        target.get_by_text("城市", exact=False),
        target.get_by_text("区域", exact=False),
        target.get_by_text("一级商家配送类型", exact=False),
    ]
    for locator in checks:
        try:
            if await locator.count() > 0:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _wait_table_ready(page: Page, timeout_ms: int = 120000) -> Page | Frame:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for target in await _iter_targets(page):
            if await _target_has_table_data(target):
                await page.wait_for_timeout(2000)
                return target
        await page.wait_for_timeout(1000)
    raise RuntimeError("表格加载超时：未检测到商家明细数据（可能页签未切换成功）")


async def _find_table_body(target: Page | Frame):
    selectors = [
        "table tbody",
        ".ant-table-tbody",
        "[class*='table-body']",
        "[class*='table-container']",
        "[class*='vtable']",
        "[class*='sheet']",
        "table",
    ]
    for selector in selectors:
        locator = target.locator(selector).first
        try:
            if await locator.count() == 0:
                continue
            box = await locator.bounding_box()
            if box and box["width"] > 100 and box["height"] > 80:
                return locator, box
        except Exception:  # noqa: BLE001
            continue
    return None, None


async def _hover_table_area(page: Page, target: Page | Frame) -> None:
    """表格需先悬停，右侧才会出现下载工具栏。"""
    body, box = await _find_table_body(target)
    if box:
        x = box["x"] + box["width"] * 0.45
        y = box["y"] + box["height"] * 0.35
        await page.mouse.move(x, y)
        await page.wait_for_timeout(1000)
        return

    cell_selectors = [
        "table tbody tr td",
        ".ant-table-tbody tr td",
        "[class*='table'] tbody tr td",
    ]
    for selector in cell_selectors:
        cell = target.locator(selector).first
        try:
            await cell.wait_for(state="visible", timeout=3000)
            await cell.hover(force=True)
            await page.wait_for_timeout(1000)
            return
        except PlaywrightTimeoutError:
            continue

    viewport = page.viewport_size or {"width": 1600, "height": 900}
    await page.mouse.move(viewport["width"] // 2, viewport["height"] // 2 + 120)
    await page.wait_for_timeout(1000)


async def _click_table_download(page: Page, target: Page | Frame) -> None:
    """悬停表格后点击右侧下载图标，再选 Excel。"""
    download_selectors = [
        '[title="下载"]',
        '[title*="下载"]',
        '[aria-label="下载"]',
        '[aria-label*="下载"]',
        '[class*="download"]',
        'i[class*="download"]',
    ]

    last_error: Optional[Exception] = None
    for _ in range(5):
        await _hover_table_area(page, target)
        clicked = False

        for scope in await _iter_targets(page):
            for selector in download_selectors:
                btn = scope.locator(selector)
                try:
                    if await btn.count() == 0:
                        continue
                    item = btn.last
                    await item.wait_for(state="visible", timeout=1500)
                    await item.click(timeout=5000)
                    clicked = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            if clicked:
                break

        if not clicked:
            _, box = await _find_table_body(target)
            if box:
                try:
                    x = box["x"] + box["width"] - 16
                    y = box["y"] + 56
                    await page.mouse.move(x, y)
                    await page.wait_for_timeout(300)
                    await page.mouse.click(x, y)
                    clicked = True
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

        if clicked:
            for scope in await _iter_targets(page):
                excel_item = scope.get_by_text("Excel", exact=False).first
                try:
                    await excel_item.wait_for(state="visible", timeout=8000)
                    await excel_item.click()
                    return
                except Exception:  # noqa: BLE001
                    continue
            last_error = RuntimeError("已点击下载，但未找到 Excel 选项")

        await page.wait_for_timeout(800)

    raise RuntimeError(f"未找到下载按钮（需先悬停表格区域）: {last_error}")


async def _save_debug_screenshot(page: Page, temp_dir: Path, name: str) -> None:
    shot = temp_dir / name
    try:
        await page.screenshot(path=str(shot), full_page=True)
        print(f"调试截图已保存: {shot}", file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


async def _download_excel_async(
    download_dir: Path,
    *,
    url: str,
    password: str,
    headless: bool,
    debug: bool,
) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            accept_downloads=True,
            viewport={"width": 1600, "height": 900},
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)

            try:
                pwd_input = page.locator('input[type="password"]').first
                await pwd_input.wait_for(timeout=5000)
                await pwd_input.fill(password)
                confirm_btn = page.get_by_role("button", name="确定").first
                await confirm_btn.click()
            except PlaywrightTimeoutError:
                pass

            await page.get_by_text("每日指标看板", exact=False).first.wait_for(timeout=120000)
            await _open_merchant_yesterday_tab(page)
            table_target = await _wait_table_ready(page)

            async with page.expect_download(timeout=120000) as download_info:
                await _click_table_download(page, table_target)
            download = await download_info.value
            suggest = download.suggested_filename or f"self_delivery_{int(time.time())}.xlsx"
            output = download_dir / suggest
            await download.save_as(str(output))
            return output
        except Exception:
            if debug:
                await _save_debug_screenshot(page, download_dir, "debug_failed.png")
            raise
        finally:
            await context.close()
            await browser.close()


def _download_excel_impl(
    download_dir: Path,
    *,
    url: str,
    password: str,
    headless: bool,
    debug: bool = False,
) -> Path:
    import asyncio

    return asyncio.run(
        _download_excel_async(
            download_dir,
            url=url,
            password=password,
            headless=headless,
            debug=debug,
        )
    )


def download_excel(
    download_dir: Path,
    *,
    url: str,
    password: str,
    headless: bool,
    debug: bool = False,
) -> Path:
    """Windows 下用子进程隔离 Playwright，避免 event loop 冲突。"""
    if sys.platform != "win32":
        return _download_excel_impl(
            download_dir,
            url=url,
            password=password,
            headless=headless,
            debug=debug,
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
    if debug:
        cmd.append("--debug")

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
    parser.add_argument("--debug", action="store_true", help="失败时保存页面截图")
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
                debug=args.debug,
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
            temp_dir,
            url=args.url,
            password=args.password,
            headless=args.headless,
            debug=args.debug,
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
