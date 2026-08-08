#!/usr/bin/env python3
"""Windows 本机定时：自配门店监控（看板下载 + pandas筛选 + 企微推送）。"""
from __future__ import annotations

import argparse
import asyncio
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
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BOARD_URL = "http://47.112.178.78:8100/#/de-link/zjygliyM?ticket=8GbVO1Vw"
BOARD_PASSWORD = "mtwm@888"
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb"

DELIVERY_ALLOWED = {"跑腿", "商家配送"}
BIZ_ALLOWED = {"城市商家", "全国KA", "区域KA"}
TARGET_CHART_TITLE = "商家明细-昨日"
REQUIRED_FIELDS = ("一级商家配送类型", "商家类型", "上线时间")
# 看板中「含配送类型+上线时间」的商家明细-昨日图表固定 ID（兜底）
FALLBACK_CHART_ID = "7425461801027899392"


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


async def _login_if_needed(page: Page, password: str) -> None:
    try:
        pwd_input = page.locator('input[type="password"]').first
        await pwd_input.wait_for(timeout=8000)
        await pwd_input.fill(password)
        for name in ("确定", "OK", "确认"):
            btn = page.get_by_role("button", name=name)
            if await btn.count() == 0:
                btn = page.get_by_text(name, exact=True)
            if await btn.count():
                await btn.first.click()
                break
    except PlaywrightTimeoutError:
        pass


async def _force_show_icons(page: Page, root_selector: str) -> None:
    await page.evaluate(
        """(rootSelector) => {
          const root = document.querySelector(rootSelector) || document;
          const nodes = root.querySelectorAll(
            '.icons-container,.bar-base-icon,.ed-dropdown,.ed-tooltip__trigger'
          );
          for (const n of nodes) {
            let p = n;
            for (let i = 0; i < 8 && p; i++) {
              const cls = String(p.className || '');
              const display = cls.includes('icons-container') ? 'flex' : 'block';
              p.style.setProperty('display', display, 'important');
              p.style.setProperty('opacity', '1', 'important');
              p.style.setProperty('visibility', 'visible', 'important');
              p.style.setProperty('pointer-events', 'auto', 'important');
              p.style.setProperty('z-index', '99999', 'important');
              p = p.parentElement;
            }
          }
        }""",
        root_selector,
    )


async def _download_excel_from_chart(page: Page, chart_id: str, download_dir: Path) -> Path:
    wrapper_sel = f"#wrapper-outer-id-{chart_id}"
    wrapper = page.locator(wrapper_sel)
    if await wrapper.count() == 0:
        raise RuntimeError(f"未找到目标图表容器: {wrapper_sel}")

    # 关闭可能残留的放大弹窗
    for _ in range(2):
        close_btn = page.locator(".ed-dialog:visible .ed-dialog__headerbtn, .ed-dialog:visible .ed-dialog__close")
        if await close_btn.count() == 0:
            break
        try:
            await close_btn.first.click(force=True, timeout=1000)
            await page.wait_for_timeout(300)
        except Exception:  # noqa: BLE001
            break

    canvas = wrapper.locator("canvas").first
    box = await canvas.bounding_box()
    if not box:
        raise RuntimeError("未找到目标图表 canvas，无法悬停")

    last_error: Optional[Exception] = None
    for attempt in range(4):
        try:
            # DataEase 明细表是 canvas：必须先悬停，右侧蓝色工具栏才会出现。
            await page.mouse.move(box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.35)
            await page.wait_for_timeout(900)
            if attempt >= 1:
                await _force_show_icons(page, wrapper_sel)

            download_btn = wrapper.locator('.bar-base-icon[role="button"]').first
            if await download_btn.count() == 0:
                await page.mouse.click(box["x"] + box["width"] - 20, box["y"] + 55)
            else:
                await download_btn.click(force=True)

            excel_item = page.locator(
                ".ed-dropdown-menu__item:visible, .ed-select-dropdown__item:visible, li:visible"
            ).filter(has_text="Excel").first
            await excel_item.wait_for(state="visible", timeout=5000)

            async with page.expect_download(timeout=180000) as download_info:
                await excel_item.click(force=True)
            download = await download_info.value
            suggest = download.suggested_filename or f"self_delivery_{int(time.time())}.xlsx"
            output = download_dir / suggest
            await download.save_as(str(output))
            if output.stat().st_size < 100:
                raise RuntimeError("下载的 Excel 文件过小，可能失败")
            return output
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

    raise RuntimeError(f"悬停后点击下载/Excel 失败: {last_error}")


async def _open_target_tab(page: Page) -> None:
    """点击底部页签，避免点到图表标题同名文本。"""
    selectors = [
        page.get_by_role("tab", name=TARGET_CHART_TITLE),
        page.locator("[class*='tab']").get_by_text(TARGET_CHART_TITLE, exact=True),
        page.locator(".ed-tabs__item, .el-tabs__item, [class*='DeTabs']").get_by_text(
            TARGET_CHART_TITLE, exact=False
        ),
        page.get_by_text(TARGET_CHART_TITLE, exact=True),
    ]
    last_error: Optional[Exception] = None
    for locator in selectors:
        try:
            if await locator.count() == 0:
                continue
            target = locator.last
            await target.scroll_into_view_if_needed(timeout=3000)
            await target.click(timeout=8000)
            await page.wait_for_timeout(2500)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"未能点击页签「{TARGET_CHART_TITLE}」: {last_error}")


async def _wait_target_chart_id(page: Page, timeout_ms: int = 120000) -> str:
    chart_id_box: dict[str, Optional[str]] = {"id": None}

    async def on_response(resp) -> None:
        if "chartData/getData" not in resp.url:
            return
        try:
            payload = await resp.json()
        except Exception:  # noqa: BLE001
            return
        data = payload.get("data") or {}
        if data.get("title") != TARGET_CHART_TITLE:
            return
        inner = data.get("data") or {}
        fields = inner.get("fields") or data.get("fields") or []
        names = {str(f.get("name") or "") for f in fields}
        if all(field in names for field in REQUIRED_FIELDS):
            chart_id_box["id"] = str(data.get("id") or "")

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    started = time.time()
    deadline = started + timeout_ms / 1000
    retried_tab = False
    while time.time() < deadline:
        if chart_id_box["id"]:
            return chart_id_box["id"]

        # DOM 兜底：目标图表容器已出现则可直接用
        fallback = page.locator(f"#wrapper-outer-id-{FALLBACK_CHART_ID}")
        if await fallback.count() > 0:
            box = await fallback.first.bounding_box()
            if box and box.get("width", 0) > 200 and box.get("height", 0) > 200:
                return FALLBACK_CHART_ID

        # 约 15 秒后再点一次页签，防止首次点到同名标题
        if (not retried_tab) and (time.time() - started) >= 15:
            try:
                await _open_target_tab(page)
                retried_tab = True
            except Exception:  # noqa: BLE001
                pass

        await page.wait_for_timeout(500)

    # 最后再尝试 fallback（即使尺寸较小）
    if await page.locator(f"#wrapper-outer-id-{FALLBACK_CHART_ID}").count() > 0:
        return FALLBACK_CHART_ID
    raise RuntimeError("等待目标图表超时：未识别到含「一级商家配送类型/上线时间」的商家明细-昨日")


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
            locale="zh-CN",
            viewport={"width": 1600, "height": 900},
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=180000)
            await _login_if_needed(page, password)
            await page.get_by_text("每日指标看板", exact=False).first.wait_for(timeout=180000)

            wait_task = asyncio.create_task(_wait_target_chart_id(page, timeout_ms=150000))
            await _open_target_tab(page)
            chart_id = await wait_task
            print(f"使用图表ID: {chart_id}", file=sys.stderr)
            await page.wait_for_timeout(2000)
            return await _download_excel_from_chart(page, chart_id, download_dir)
        except Exception:
            if debug:
                shot = download_dir / "debug_failed.png"
                try:
                    await page.screenshot(path=str(shot), full_page=True)
                    print(f"调试截图已保存: {shot}", file=sys.stderr)
                except Exception:  # noqa: BLE001
                    pass
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

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=420, check=False)
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

    # 优先按列名；兼容你原来的 C/G/R 列约定。
    col_delivery = _pick_column(df, ["一级商家配送类型", "配送类型"], fallback_index=2)
    col_biz = _pick_column(df, ["商家类型"], fallback_index=6)
    col_online = _pick_column(df, ["上线时间"], fallback_index=17)

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
    store_col = _pick_column(month_df, ["商家名称", "门店", "门店名称", "store"], fallback_index=8)
    id_col = _pick_column(month_df, ["商家ID", "ID", "门店ID", "store_id"], fallback_index=7)

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
