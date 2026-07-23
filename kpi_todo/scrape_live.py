#!/usr/bin/env python3
"""登录后台，筛选川藏一区+本月，抓取 KPI 待办表格 JSON（含翻页）。"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ADMIN_SIGNIN_URL,
    ADMIN_USER,
    KPI_TODO_ADMIN_URL,
    KPI_TODO_SCRAPE_DIR,
    REGION_NAME,
)

SCRAPE_JS = """
(() => {
  const table = document.querySelector('.ant-table-tbody')
    ? document.querySelector('.ant-table')
    : document.querySelector('table');
  const root = table || document;
  const headers = Array.from(root.querySelectorAll('thead th'))
    .map(el => el.innerText.trim()).filter(Boolean);
  const rows = Array.from(root.querySelectorAll('tbody tr'))
    .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
    .filter(r => r.some(c => String(c || '').trim()));
  const totalText = document.querySelector('.ant-pagination-total-text')?.innerText || '';
  return {
    headers,
    rows,
    totalText,
    scraped_at: new Date().toISOString(),
    filters: { region: '川藏一区', period: '本月' }
  };
})()
"""


def _click_option(page, label: str) -> bool:
    for locator in [
        page.get_by_role("option", name=label, exact=True),
        page.locator(".ant-select-item-option-content", has_text=label),
        page.get_by_text(label, exact=True),
    ]:
        try:
            if locator.count() > 0:
                locator.first.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def _set_filter(page, keywords: list[str], value: str) -> bool:
    for kw in keywords:
        try:
            containers = page.locator(f"text={kw}")
            if containers.count() == 0:
                continue
            container = containers.first
            parent = container.locator("xpath=ancestor::div[contains(@class,'ant-form-item')][1]")
            if parent.count() == 0:
                parent = container.locator("xpath=..")
            select = parent.locator(".ant-select, .ant-picker, input, [role='combobox']").first
            if select.count() > 0:
                select.click(timeout=5000)
                time.sleep(0.5)
                if _click_option(page, value):
                    time.sleep(0.8)
                    return True
        except Exception:
            continue
    return _click_option(page, value)


def _set_filter_by_label(page, label: str, value: str) -> bool:
    script = """
({ label, value }) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => String(s || '').replace(/\\s+/g, '');
  return (async () => {
    const labels = Array.from(document.querySelectorAll('.ant-form-item-label label, .ant-form-item-label'));
    const target = labels.find((el) => norm(el.innerText).includes(norm(label)));
    if (!target) return false;
    const item = target.closest('.ant-form-item');
    const selector = item?.querySelector('.ant-select-selector, .ant-picker-input input, input');
    if (!selector) return false;
    selector.click();
    await sleep(500);
    const options = Array.from(document.querySelectorAll('.ant-select-item-option-content'));
    const opt = options.find((el) => norm(el.innerText) === norm(value))
      || options.find((el) => norm(el.innerText).includes(norm(value)));
    if (!opt) return false;
    opt.click();
    await sleep(500);
    return true;
  })();
}
"""
    try:
        return bool(page.evaluate(script, {"label": label, "value": value}))
    except Exception:
        return False


def _set_page_size(page, size: int = 100) -> bool:
    """把分页改为 size 条/页。"""
    try:
        # 分页区的 pageSize 下拉
        opts = page.locator(".ant-pagination-options .ant-select")
        if opts.count() == 0:
            opts = page.locator(".ant-pagination .ant-select").last
        if opts.count() == 0:
            return False
        opts.first.click(timeout=5000)
        time.sleep(0.4)
        label = f"{size} 条/页"
        if not _click_option(page, label):
            # 有的主题写成 "100条/页"
            if not _click_option(page, f"{size}条/页"):
                return False
        time.sleep(2)
        return True
    except Exception:
        return False


def _click_next_page(page) -> bool:
    nxt = page.locator(".ant-pagination-next:not(.ant-pagination-disabled)")
    if nxt.count() == 0:
        return False
    try:
        nxt.first.click(timeout=5000)
        time.sleep(2.5)
        return True
    except Exception:
        return False


def _normalize_row(headers: list[str], row: list) -> list[str] | None:
    if not isinstance(row, list):
        return None
    work = list(row)
    if len(work) > len(headers) and str(work[0] or "").strip().isdigit():
        work = work[1:]
    if len(work) > len(headers):
        work = work[: len(headers)]
    if not any(str(x or "").strip() for x in work):
        return None
    # pad
    while len(work) < len(headers):
        work.append("")
    return [str(x or "").strip() for x in work]


def _row_key(row: list[str]) -> tuple:
    # 用关键列去重
    return tuple(row[:12])


def _filter_rows(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    region_idx = headers.index("区域") if "区域" in headers else None
    end_idx = headers.index("考核结束") if "考核结束" in headers else None
    current_month = date.today().strftime("%Y-%m")
    out: list[list[str]] = []
    for row in rows:
        work = _normalize_row(headers, row)
        if work is None:
            continue
        if region_idx is not None:
            region = work[region_idx] if region_idx < len(work) else ""
            if region and region != REGION_NAME:
                continue
        if end_idx is not None:
            end_date = work[end_idx] if end_idx < len(work) else ""
            if end_date and not end_date.startswith(current_month):
                continue
        out.append(work)
    return out


def scrape(out_path: Path | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    out_path = out_path or (KPI_TODO_SCRAPE_DIR / "latest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1800, "height": 1200})
        page = context.new_page()

        page.goto(ADMIN_SIGNIN_URL, wait_until="networkidle", timeout=120000)
        if "/signin" in page.url:
            page.get_by_placeholder("用户名/邮箱").fill(ADMIN_USER)
            page.get_by_placeholder("密码").fill(ADMIN_PASSWORD)
            page.get_by_role("button", name="action-Action-登录").click()
            page.wait_for_url(lambda u: "/signin" not in u, timeout=60000)

        page.goto(KPI_TODO_ADMIN_URL, wait_until="networkidle", timeout=120000)
        time.sleep(3)

        # 先「考核结束=本月」，再「区域=川藏一区」
        period_ok = _set_filter_by_label(page, "考核结束", "本月")
        if not period_ok:
            period_ok = _set_filter(page, ["考核结束", "日期", "时间", "周期"], "本月")
        time.sleep(1)
        region_ok = _set_filter_by_label(page, "区域", REGION_NAME)
        if not region_ok:
            region_ok = _set_filter(page, ["区域", "大区", "区域名称"], REGION_NAME)

        # 等表格刷新
        time.sleep(20)
        try:
            page.wait_for_selector("tbody tr", timeout=60000)
        except Exception:
            pass
        time.sleep(10)

        page_size_ok = _set_page_size(page, 100)
        time.sleep(5)

        all_rows: list[list[str]] = []
        headers: list[str] = []
        total_text = ""
        pages = 0
        seen: set[tuple] = set()

        for _ in range(50):  # 安全上限
            chunk = page.evaluate(SCRAPE_JS)
            pages += 1
            if not headers:
                headers = [str(h or "").strip() for h in (chunk.get("headers") or []) if str(h or "").strip()]
            total_text = chunk.get("totalText") or total_text
            for row in chunk.get("rows") or []:
                work = _normalize_row(headers, row)
                if work is None:
                    continue
                key = _row_key(work)
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(work)
            if not _click_next_page(page):
                break

        browser.close()

    if not headers:
        raise RuntimeError("未解析到表头")
    if not all_rows:
        raise RuntimeError(f"抓取到 0 行数据，headers={headers}")

    filtered = _filter_rows(headers, all_rows)
    # 若筛选控件失败导致结果过多，仍用过滤后的；若过滤后为 0 则报错
    if not filtered:
        raise RuntimeError(
            f"筛选后无数据：raw={len(all_rows)} period_ok={period_ok} region_ok={region_ok} total={total_text}"
        )

    payload = {
        "headers": headers,
        "rows": filtered,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "filters": {"region": REGION_NAME, "period": "本月"},
        "filter_apply": {
            "period_ok": period_ok,
            "region_ok": region_ok,
            "page_size_ok": page_size_ok,
            "pages": pages,
            "raw_rows": len(all_rows),
            "filtered_rows": len(filtered),
            "total_text": total_text,
        },
        "page_url": KPI_TODO_ADMIN_URL,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    try:
        payload = scrape()
        print(
            json.dumps(
                {
                    "ok": True,
                    "rows": len(payload.get("rows", [])),
                    "headers": payload.get("headers"),
                    "filter_apply": payload.get("filter_apply"),
                    "out": str(KPI_TODO_SCRAPE_DIR / "latest.json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
