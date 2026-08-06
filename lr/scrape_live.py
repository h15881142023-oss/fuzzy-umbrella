#!/usr/bin/env python3
"""本机：登录后台，筛选川藏一区+目标日，抓取 LR 日利润表 JSON。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ADMIN_USER,
    LR_ADMIN_SIGNIN_URL,
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
    filters: { region: '川藏一区', date: 'target' }
  };
})()
"""


def _set_region_filter(page, region: str) -> bool:
  """区域控件是 input（非 ant-select）。"""
  try:
    item = page.locator(".ant-form-item").filter(has_text="区域").first
    inp = item.locator("input").first
    if inp.count() == 0:
      return False
    inp.click()
    inp.fill(region)
    time.sleep(0.4)
    # 下拉选项（若有）
    opt = page.locator(".ant-select-item-option-content, [role=option]", has_text=region)
    if opt.count():
      opt.first.click()
    else:
      inp.press("Enter")
    time.sleep(0.5)
    return True
  except Exception:
    return False


def _set_date_filter(page, target: date) -> dict:
  """日期：相对词（昨天/今天）或「指定日期」+ DatePicker。"""
  yesterday = date.today() - timedelta(days=1)
  today = date.today()
  tried: list[dict] = []

  try:
    date_item = page.locator(".ant-form-item").filter(has_text="日期").first
    date_item.locator(".ant-select").first.click()
    time.sleep(0.4)
  except Exception as exc:
    return {"ok": False, "value": None, "tried": [{"error": str(exc)}]}

  # 相对日期快捷项
  relative: str | None = None
  if target == yesterday:
    relative = "昨天"
  elif target == today:
    relative = "今天"

  if relative:
    try:
      opt = page.locator(
        ".ant-select-dropdown:not(.ant-select-dropdown-hidden) [role=option]",
        has_text=relative,
      ).first
      opt.click()
      time.sleep(0.6)
      tried.append({"value": relative, "ok": True})
      return {"ok": True, "value": relative, "tried": tried}
    except Exception as exc:
      tried.append({"value": relative, "ok": False, "error": str(exc)})
      # 重新打开下拉
      try:
        date_item.locator(".ant-select").first.click()
        time.sleep(0.4)
      except Exception:
        pass

  # 指定日期
  try:
    page.locator(
      ".ant-select-dropdown:not(.ant-select-dropdown-hidden) [role=option]",
      has_text="指定日期",
    ).first.click()
    time.sleep(0.6)
    picker = page.locator(".ant-picker input").first
    picker.click()
    picker.fill("")
    iso = target.isoformat()
    picker.type(iso, delay=30)
    picker.press("Enter")
    time.sleep(0.4)
    page.keyboard.press("Tab")
    time.sleep(0.4)
    val = picker.input_value()
    ok = iso in (val or "")
    tried.append({"value": f"指定日期:{iso}", "ok": ok, "picker": val})
    return {"ok": ok, "value": f"指定日期:{iso}", "tried": tried}
  except Exception as exc:
    tried.append({"value": "指定日期", "ok": False, "error": str(exc)})
    return {"ok": False, "value": None, "tried": tried}


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

    region_ok = _set_region_filter(page, REGION_NAME)
    date_info = _set_date_filter(page, target)
    # 表格异步加载
    time.sleep(35)

    payload = page.evaluate(SCRAPE_JS)
    payload["filter_apply"] = {
      "region_ok": region_ok,
      "date_ok": date_info["ok"],
      "date_value": date_info["value"],
      "date_tried": date_info["tried"],
    }
    payload["page_url"] = page.url
    payload["target_date"] = date_label
    browser.close()

  if not payload.get("rows"):
    raise RuntimeError(f"抓取到 0 行数据，headers={payload.get('headers')}")

  out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  # 同时更新 latest.json，方便本机流水线
  latest = LR_SCRAPE_DIR / "latest.json"
  if out_path.resolve() != latest.resolve():
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  return payload


def main() -> int:
  parser = argparse.ArgumentParser(description="抓取 LR 日利润表")
  parser.add_argument("--target-date", help="YYYY-MM-DD，默认昨天")
  parser.add_argument("--out", type=Path, default=None, help="输出 JSON 路径")
  args = parser.parse_args()
  target = (
    datetime.strptime(args.target_date, "%Y-%m-%d").date()
    if args.target_date
    else date.today() - timedelta(days=1)
  )
  try:
    payload = scrape(out_path=args.out, target_date=target)
    out = args.out or (LR_SCRAPE_DIR / "latest.json")
    print(json.dumps({
      "ok": True,
      "target_date": target.isoformat(),
      "rows": len(payload.get("rows", [])),
      "headers": payload.get("headers"),
      "filter_apply": payload.get("filter_apply"),
      "out": str(out),
    }, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
