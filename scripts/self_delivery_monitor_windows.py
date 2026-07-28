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


def download_excel(download_dir: Path, *, url: str, password: str, headless: bool) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
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
        page.wait_for_timeout(3000)

        with page.expect_download(timeout=60000) as download_info:
            _click_text(page, "下载", timeout_ms=30000)
            _click_text(page, "Excel", timeout_ms=10000)
        download = download_info.value
        suggest = download.suggested_filename or f"self_delivery_{int(time.time())}.xlsx"
        output = download_dir / suggest
        download.save_as(str(output))

        context.close()
        browser.close()
        return output


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
    args = parser.parse_args()

    temp_dir = Path(args.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
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
