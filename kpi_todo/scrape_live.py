#!/usr/bin/env python3
"""登录后台，筛选川藏一区+本月，抓取 KPI 待办表格 JSON。"""
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
)

SCRAPE_JS = """
(() => {
  const headers = Array.from(document.querySelectorAll('thead th'))
    .map(el => el.innerText.trim()).filter(Boolean);
  const rows = Array.from(document.querySelectorAll('tbody tr'))
    .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
    .filter(r => r.length);
  return {
    headers,
    rows,
    scraped_at: new Date().toISOString(),
    filters: { region: '川藏一区', period: '本月' }
  };
})()
"""


def _click_option(page, label: str) -> bool:
  """点击下拉或筛选项。"""
  for locator in [
    page.get_by_text(label, exact=True),
    page.get_by_role("option", name=label),
    page.locator(f"text={label}"),
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
          time.sleep(0.5)
          return True
    except Exception:
      continue
  # 兜底：直接点页面上可见的选项
  return _click_option(page, value)


def _set_filter_by_label(page, label: str, value: str) -> bool:
  """按筛选标签精确点击下拉并选择值。"""
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
    await sleep(400);
    const options = Array.from(document.querySelectorAll('.ant-select-item-option-content'));
    const opt = options.find((el) => norm(el.innerText) === norm(value));
    if (!opt) return false;
    opt.click();
    await sleep(400);
    return true;
  })();
}
"""
  try:
    return bool(page.evaluate(script, {"label": label, "value": value}))
  except Exception:
    return False


def scrape(out_path: Path | None = None) -> dict:
  from playwright.sync_api import sync_playwright

  out_path = out_path or (KPI_TODO_SCRAPE_DIR / "latest.json")
  out_path.parent.mkdir(parents=True, exist_ok=True)

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    page = context.new_page()

    page.goto(ADMIN_SIGNIN_URL, wait_until="networkidle", timeout=120000)
    if "/signin" in page.url:
      page.get_by_placeholder("用户名/邮箱").fill(ADMIN_USER)
      page.get_by_placeholder("密码").fill(ADMIN_PASSWORD)
      page.get_by_role("button", name="action-Action-登录").click()
      page.wait_for_url(lambda u: "/signin" not in u, timeout=60000)

    page.goto(KPI_TODO_ADMIN_URL, wait_until="networkidle", timeout=120000)
    time.sleep(3)

    # 按用户确认顺序：先「指定日期」下拉选「本月」，再选区域。
    period_ok = _set_filter_by_label(page, "考核结束", "本月")
    if not period_ok:
      period_ok = _set_filter(page, ["考核结束", "日期", "时间", "周期"], "本月")
    region_ok = _set_filter_by_label(page, "区域", "川藏一区")
    if not region_ok:
      region_ok = _set_filter(page, ["区域", "大区", "区域名称"], "川藏一区")
    time.sleep(45)

    payload = page.evaluate(SCRAPE_JS)
    payload["filter_apply"] = {"period_ok": period_ok, "region_ok": region_ok}
    payload["page_url"] = page.url
    browser.close()

  if not payload.get("rows"):
    raise RuntimeError(f"抓取到 0 行数据，headers={payload.get('headers')}")

  headers = [str(h or "").strip() for h in payload.get("headers") or []]
  region_idx = headers.index("区域") if "区域" in headers else None
  end_idx = headers.index("考核结束") if "考核结束" in headers else None
  current_month = date.today().strftime("%Y-%m")
  filtered: list[list[str]] = []
  for row in payload.get("rows") or []:
    if not isinstance(row, list):
      continue
    work_row = list(row)
    # 页面存在前置序号列且 header 未包含该列，做一次对齐。
    if len(work_row) > len(headers) and str(work_row[0] or "").strip().isdigit():
      work_row = work_row[1:]
    # 某些场景末尾会多一列空白操作列，裁到与 header 等长。
    if len(work_row) > len(headers):
      work_row = work_row[: len(headers)]
    if not any(str(x or "").strip() for x in row):
      continue
    if region_idx is not None:
      region = str(work_row[region_idx] or "").strip() if region_idx < len(work_row) else ""
      if region != "川藏一区":
        continue
    if end_idx is not None:
      end_date = str(work_row[end_idx] or "").strip() if end_idx < len(work_row) else ""
      if end_date and not end_date.startswith(current_month):
        continue
    filtered.append(work_row)
  payload["rows"] = filtered

  out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  return payload


def main() -> int:
  try:
    payload = scrape()
    print(json.dumps({
      "ok": True,
      "rows": len(payload.get("rows", [])),
      "headers": payload.get("headers"),
      "out": str(KPI_TODO_SCRAPE_DIR / "latest.json"),
    }, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
