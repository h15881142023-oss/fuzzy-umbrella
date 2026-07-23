#!/usr/bin/env python3
"""本机：登录后台，筛选川藏一区+昨天，抓取 LR 日利润表 JSON。"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ADMIN_SIGNIN_URL,
    ADMIN_USER,
    LR_ADMIN_URL,
    LR_SCRAPE_DIR,
    REGION_NAME,
)

SCRAPE_JS = """
(() => {
  const tables = Array.from(document.querySelectorAll('table'));
  let best = null;
  for (const table of tables) {
    const headers = Array.from(table.querySelectorAll('thead th'))
      .map(el => el.innerText.trim());
    const headerText = headers.join('|');
    if (!headerText.includes('原价交易额') && !headerText.includes('商品原价')) continue;
    const style = window.getComputedStyle(table);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const rows = Array.from(table.querySelectorAll('tbody tr'))
      .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
      .filter(r => r.some(c => c));
    if (!best || rows.length > best.rows.length) {
      best = { headers, rows };
    }
  }
  if (!best) {
    const headers = Array.from(document.querySelectorAll('thead th'))
      .map(el => el.innerText.trim()).filter(Boolean);
    const rows = Array.from(document.querySelectorAll('tbody tr'))
      .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
      .filter(r => r.length);
    best = { headers, rows };
  }
  return {
    headers: best.headers,
    rows: best.rows,
    scraped_at: new Date().toISOString(),
    filters: { region: '川藏一区', date: '昨天' }
  };
})()
"""


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
    await sleep(400);
    const options = Array.from(document.querySelectorAll('.ant-select-item-option-content'));
    const opt = options.find((el) => norm(el.innerText) === norm(value) || norm(el.innerText).includes(norm(value)));
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


def scrape(out_path: Path | None = None, target_date: date | None = None) -> dict:
  from playwright.sync_api import sync_playwright

  target = target_date or (date.today() - timedelta(days=1))
  out_path = out_path or (LR_SCRAPE_DIR / "latest.json")
  out_path.parent.mkdir(parents=True, exist_ok=True)
  date_label = target.isoformat()

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

    page.goto(LR_ADMIN_URL, wait_until="networkidle", timeout=120000)
    time.sleep(3)

    region_ok = _set_filter_by_label(page, "区域", REGION_NAME)
    # 优先选「昨天」，失败再尝试具体日期
    date_ok = _set_filter_by_label(page, "日期", "昨天")
    if not date_ok:
      date_ok = _set_filter_by_label(page, "日期", date_label)
    time.sleep(45)

    payload = page.evaluate(SCRAPE_JS)
    payload["filter_apply"] = {"region_ok": region_ok, "date_ok": date_ok}
    payload["page_url"] = page.url
    payload["target_date"] = date_label
    browser.close()

  if not payload.get("rows"):
    raise RuntimeError(f"抓取到 0 行数据，headers={payload.get('headers')}")

  out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  return payload


def main() -> int:
  try:
    payload = scrape()
    print(json.dumps({
      "ok": True,
      "rows": len(payload.get("rows", [])),
      "headers": payload.get("headers"),
      "out": str(LR_SCRAPE_DIR / "latest.json"),
    }, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
