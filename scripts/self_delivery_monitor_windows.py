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


@dataclass
class ChartCapture:
    chart_id: str
    chart_req: dict
    headers: list[str]
    link_token: str


DE_EXPORT_URL = "http://47.112.178.78:8100/de2api/chartData/innerExportDetails"
DE_REFERER = "http://47.112.178.78:8100/"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


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


class _ChartListener:
    """在 goto 之前挂上，避免错过首屏 getData。"""

    def __init__(self) -> None:
        self.link_token: Optional[str] = None
        self.pending_req: dict[str, dict] = {}
        self.captures: list[ChartCapture] = []
        self.seen: list[str] = []

    def attach(self, page: Page) -> None:
        def on_request(req) -> None:
            headers = dict(req.headers)
            token = headers.get("x-de-link-token")
            if token:
                self.link_token = token
            if not req.url.endswith("/de2api/chartData/getData"):
                return
            raw = req.post_data
            if not raw:
                return
            try:
                body = json.loads(raw)
            except Exception:  # noqa: BLE001
                return
            chart_id = str(body.get("id") or "")
            if chart_id:
                self.pending_req[chart_id] = body

        async def on_response(resp) -> None:
            req_headers = dict(resp.request.headers)
            if req_headers.get("x-de-link-token"):
                self.link_token = req_headers["x-de-link-token"]
            if not resp.url.endswith("/de2api/chartData/getData"):
                return
            try:
                payload = await resp.json()
            except Exception as exc:  # noqa: BLE001
                self.seen.append(f"json_err:{exc}")
                return
            data = payload.get("data") or {}
            title = str(data.get("title") or "")
            chart_id = str(data.get("id") or "")
            inner = data.get("data") or {}
            fields = inner.get("fields") or data.get("fields") or []
            names = {str(f.get("name") or "") for f in fields}
            self.seen.append(f"{title}|{chart_id}|fields={len(names)}")
            if title != TARGET_CHART_TITLE:
                return
            if not all(field in names for field in REQUIRED_FIELDS):
                missing = [f for f in REQUIRED_FIELDS if f not in names]
                self.seen.append(f"skip:{chart_id}:missing={missing}")
                return
            chart_req = self.pending_req.get(chart_id)
            if chart_req is None:
                raw = resp.request.post_data
                if raw:
                    try:
                        chart_req = json.loads(raw)
                    except Exception:  # noqa: BLE001
                        chart_req = None
            if not chart_req:
                self.seen.append(f"skip:{chart_id}:no_req_body")
                return
            headers = [str(f.get("name") or "") for f in fields]
            capture = ChartCapture(
                chart_id=chart_id or str(chart_req.get("id") or ""),
                chart_req=chart_req,
                headers=headers,
                link_token=self.link_token or "",
            )
            self.captures.append(capture)

        page.on("request", on_request)
        page.on("response", lambda r: asyncio.create_task(on_response(r)))

    def best_capture(self) -> Optional[ChartCapture]:
        if not self.captures:
            return None
        for item in reversed(self.captures):
            if item.chart_id == FALLBACK_CHART_ID:
                if self.link_token:
                    item.link_token = self.link_token
                return item
        item = self.captures[-1]
        if self.link_token:
            item.link_token = self.link_token
        return item


async def _wait_target_chart(page: Page, listener: _ChartListener, timeout_ms: int = 150000) -> ChartCapture:
    """等待目标图表加载，并捕获 API 导出所需的 token 与请求体。"""
    started = time.time()
    deadline = started + timeout_ms / 1000
    next_tab_retry = started + 12
    tab_retries = 0
    while time.time() < deadline:
        captured = listener.best_capture()
        if captured:
            return captured

        now = time.time()
        if now >= next_tab_retry and tab_retries < 4:
            tab_retries += 1
            _log(f"重新点击页签「{TARGET_CHART_TITLE}」（第 {tab_retries} 次）…")
            try:
                await _open_target_tab(page)
            except Exception as exc:  # noqa: BLE001
                _log(f"页签点击失败: {exc}")
            next_tab_retry = now + 20

        # DOM 兜底：目标图表容器已出现
        fallback = page.locator(f"#wrapper-outer-id-{FALLBACK_CHART_ID}")
        if await fallback.count() > 0:
            box = await fallback.first.bounding_box()
            if box and box.get("width", 0) > 200 and box.get("height", 0) > 200:
                _log(f"DOM 已出现兜底图表容器 {FALLBACK_CHART_ID}，继续等待 getData…")

        await page.wait_for_timeout(500)

    captured = listener.best_capture()
    if captured:
        return captured
    seen = "; ".join(listener.seen[-12:]) or "无"
    raise RuntimeError(
        "等待目标图表超时：未识别到含「一级商家配送类型/上线时间」的商家明细-昨日；"
        f"已观察到: {seen}"
    )


async def _resolve_link_token(page: Page, capture: ChartCapture, listener: _ChartListener) -> ChartCapture:
    """补全 link token（部分环境下 wait 阶段可能尚未捕获）。"""
    if capture.link_token or listener.link_token:
        capture.link_token = capture.link_token or listener.link_token or ""
        return capture

    token_box: dict[str, Optional[str]] = {"value": None}

    def grab(req) -> None:
        token = dict(req.headers).get("x-de-link-token")
        if token:
            token_box["value"] = token

    page.on("request", grab)
    for _ in range(6):
        if token_box["value"] or listener.link_token:
            break
        await page.wait_for_timeout(500)

    if not token_box["value"] and not listener.link_token:
        try:
            await _open_target_tab(page)
        except Exception:  # noqa: BLE001
            pass
        for _ in range(20):
            if token_box["value"] or listener.link_token:
                break
            await page.wait_for_timeout(500)

    capture.link_token = token_box["value"] or listener.link_token or capture.link_token
    return capture


async def _export_excel_via_api(
    page: Page,
    capture: ChartCapture,
    download_dir: Path,
) -> Path:
    """通过 DataEase innerExportDetails API 导出 Excel，不依赖 canvas 悬停。"""
    if not capture.link_token:
        raise RuntimeError("缺少 x-de-link-token，无法调用 DataEase 导出 API")

    view_name = (
        f"每日指标看板-乔显海_{TARGET_CHART_TITLE}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    payload = {
        "proxy": None,
        "dvId": capture.chart_req["sceneId"],
        "viewId": capture.chart_id,
        "viewInfo": capture.chart_req,
        "viewName": view_name,
        "busiFlag": "dashboard",
        "downloadType": None,
        "header": capture.headers,
        "details": [],
        "excelTypes": [0] * len(capture.headers),
        "excelHeaderKeys": capture.headers,
        "detailFields": [],
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "x-de-link-token": capture.link_token,
        "Referer": DE_REFERER,
    }
    resp = await page.request.post(
        DE_EXPORT_URL,
        data=json.dumps(payload, ensure_ascii=False),
        headers=headers,
        timeout=180000,
    )
    if resp.status != 200:
        body = (await resp.text())[:500]
        raise RuntimeError(f"DataEase API 导出失败: HTTP {resp.status} {body}")

    data = await resp.body()
    if len(data) < 100 or not data.startswith(b"PK"):
        body = data[:200].decode("utf-8", errors="replace")
        raise RuntimeError(f"DataEase API 返回非 Excel 内容: {body}")

    output = download_dir / f"{view_name}.xlsx"
    output.write_bytes(data)
    return output


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
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = await browser.new_context(
            accept_downloads=True,
            locale="zh-CN",
            viewport={"width": 1600, "height": 900},
        )
        page = await context.new_page()
        listener = _ChartListener()
        listener.attach(page)
        last_error: Optional[Exception] = None
        try:
            _log("启动 Chromium…")
            _log(f"打开看板: {url}")
            # DataEase 是 SPA：先 load，再尽量等 networkidle（失败不阻断）
            await page.goto(url, wait_until="load", timeout=180000)
            try:
                await page.wait_for_load_state("networkidle", timeout=90000)
            except PlaywrightTimeoutError:
                _log("networkidle 超时，继续后续流程…")
            _log("页面已加载，检查密码弹窗…")
            await _login_if_needed(page, password)
            # 看板标题或目标页签任一出现即可
            try:
                await page.get_by_text("每日指标看板", exact=False).first.wait_for(timeout=120000)
            except PlaywrightTimeoutError:
                _log("未看到「每日指标看板」标题，尝试直接找页签…")
                await page.get_by_text(TARGET_CHART_TITLE, exact=False).first.wait_for(timeout=60000)
            _log("看板标题已出现，等待「商家明细-昨日」…")

            try:
                await _open_target_tab(page)
            except Exception as exc:  # noqa: BLE001
                _log(f"首次页签点击失败，继续等待网络数据: {exc}")

            try:
                capture = await _wait_target_chart(page, listener, timeout_ms=120000)
                capture = await _resolve_link_token(page, capture, listener)
                _log(
                    f"使用图表ID: {capture.chart_id}（API 导出, token={'有' if capture.link_token else '无'}）"
                )
                await page.wait_for_timeout(1000)

                for attempt in range(2):
                    try:
                        _log(f"开始 API 导出（第 {attempt + 1} 次）…")
                        path = await _export_excel_via_api(page, capture, download_dir)
                        _log(f"API 导出完成: {path.name} ({path.stat().st_size} bytes)")
                        return path
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        _log(f"API 导出第 {attempt + 1} 次失败: {exc}")
                        await page.wait_for_timeout(1500)

                _log("API 导出失败，回退 canvas 悬停下载")
                return await _download_excel_from_chart(page, capture.chart_id, download_dir)
            except Exception as api_exc:  # noqa: BLE001
                last_error = api_exc
                _log(f"API 路径失败: {api_exc}")
                _log(f"尝试 DOM 兜底悬停下载 chart={FALLBACK_CHART_ID}")
                try:
                    await _open_target_tab(page)
                except Exception:  # noqa: BLE001
                    pass
                await page.wait_for_timeout(2000)
                if await page.locator(f"#wrapper-outer-id-{FALLBACK_CHART_ID}").count() == 0:
                    raise RuntimeError(f"DataEase 数据下载失败: {last_error}") from api_exc
                return await _download_excel_from_chart(page, FALLBACK_CHART_ID, download_dir)
        except Exception:
            if debug:
                shot = download_dir / "debug_failed.png"
                try:
                    await page.screenshot(path=str(shot), full_page=True)
                    _log(f"调试截图已保存: {shot}")
                except Exception:  # noqa: BLE001
                    pass
                diag = download_dir / "debug_seen.txt"
                try:
                    diag.write_text("\n".join(listener.seen) or "(empty)", encoding="utf-8")
                    _log(f"网络观测已保存: {diag}")
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
        "-u",
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

    # 实时透传子进程输出，避免 Windows 定时/手动跑时长时间无日志。
    _log("启动子进程下载 DataEase Excel…")
    proc = subprocess.run(cmd, timeout=420, check=False)
    if proc.returncode != 0:
        raise RuntimeError("浏览器下载子进程失败（详见上方日志）")

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


def push_failure_alert(webhook: str, error: str) -> None:
    """下载或推送失败时发送企微告警（忽略告警发送本身的失败）。"""
    today = date.today().isoformat()
    text = f"❌ 自配监控：DataEase数据下载失败\n> 日期：{today}\n> 原因：{error[:500]}"
    try:
        _post_json(webhook, {"msgtype": "text", "text": {"content": text}})
    except Exception as alert_exc:  # noqa: BLE001
        print(f"失败告警发送异常: {alert_exc}", file=sys.stderr, flush=True)


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
    _log(f"自配监控启动 headless={args.headless} debug={args.debug} temp={temp_dir}")

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
            _log(f"download-only 完成: {downloaded}")
            return 0
        except Exception as exc:  # noqa: BLE001
            _log(f"执行失败: {exc}")
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
        _log("开始筛选 Excel…")
        result = build_filtered_result(downloaded_excel, temp_dir)
        filtered_excel = result.recent_file
        _log(f"筛选完成 当月={result.month_count} 近3天={result.recent_count}，开始推送企微…")
        push_resp = push_wecom(args.webhook, result)
        print(json.dumps(push_resp, ensure_ascii=False, indent=2), flush=True)

        # 仅在推送成功（errcode=0）后删除临时 Excel。
        safe_unlink(downloaded_excel)
        safe_unlink(filtered_excel)
        _log("推送成功，临时文件已清理")
        return 0
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        _log(f"执行失败: {err_text}")
        push_failure_alert(args.webhook, err_text)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
