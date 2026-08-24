#!/usr/bin/env python3
"""本机：登录后台，筛选川藏一区+目标日，抓取 LR 日利润表 JSON。"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

import config as _cfg  # noqa: E402

# getattr：本机 config 被旧文件覆盖缺字段时仍可用默认账号
ADMIN_USER = getattr(_cfg, "ADMIN_USER", None) or os.environ.get("ADMIN_USER", "qiaoxianhai")
ADMIN_PASSWORD = getattr(_cfg, "ADMIN_PASSWORD", None) or os.environ.get(
    "ADMIN_PASSWORD", "123"
)
LR_ADMIN_URL = getattr(_cfg, "LR_ADMIN_URL", None) or os.environ.get(
    "LR_ADMIN_URL", "http://www.chuxin.city/v/admin/g303bjgeytq"
)
LR_ADMIN_SIGNIN_URL = getattr(_cfg, "LR_ADMIN_SIGNIN_URL", None) or os.environ.get(
    "LR_ADMIN_SIGNIN_URL", "http://www.chuxin.city/v/signin"
)
REGION_NAME = getattr(_cfg, "REGION_NAME", None) or "川藏一区"
LR_SCRAPE_DIR = Path(
    getattr(_cfg, "LR_SCRAPE_DIR", None)
    or os.environ.get("LR_SCRAPE_DIR", str(ROOT / "data" / "lr_scrape"))
)

# 新站（chuxin.city）表格主区域；避免把日期面板里的日历 table 当成数据表
SCRAPE_JS = """
(() => {
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const thead = document.querySelector('.ant-table-thead');
  const tbody = document.querySelector('.ant-table-tbody');
  if (thead && tbody) {
    const headers = Array.from(thead.querySelectorAll('th')).map(el => norm(el.innerText));
    const rows = Array.from(tbody.querySelectorAll(':scope > tr'))
      .map(tr => Array.from(tr.querySelectorAll('td')).map(td => norm(td.innerText)))
      .filter(r => r.some(c => c));
    return {
      headers,
      rows,
      table_count: document.querySelectorAll('table').length,
      body_snip: norm(document.body && document.body.innerText || '').slice(0, 400),
      scraped_at: new Date().toISOString(),
      filters: { region: '川藏一区', date: 'target' }
    };
  }
  const tables = Array.from(document.querySelectorAll('table'));
  let best = null;
  for (const table of tables) {
    if (table.closest('.ant-picker-dropdown, .ant-picker-panel')) continue;
    const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th'))
      .map(el => norm(el.innerText));
    const headerText = headers.join('|');
    const style = window.getComputedStyle(table);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const rows = Array.from(table.querySelectorAll('tbody tr'))
      .map(tr => Array.from(tr.querySelectorAll('td')).map(td => norm(td.innerText)))
      .filter(r => r.some(c => c));
    const score =
      (headerText.includes('原价交易额') || headerText.includes('商品原价') || headerText.includes('区域') ? 1000 : 0)
      + rows.length;
    if (!best || score > best.score) {
      best = { headers, rows, score };
    }
  }
  if (!best) best = { headers: [], rows: [], score: 0 };
  return {
    headers: best.headers,
    rows: best.rows,
    table_count: tables.length,
    body_snip: norm(document.body && document.body.innerText || '').slice(0, 400),
    scraped_at: new Date().toISOString(),
    filters: { region: '川藏一区', date: 'target' }
  };
})()
"""


def _click_password_login(page) -> None:
  """点密码登录。新站按钮文案是「登 录」（中间有空格），勿点「企业微信登录」。"""
  buttons = page.locator("button")
  n = buttons.count()
  for i in range(n):
    btn = buttons.nth(i)
    text = (btn.inner_text() or "").replace("\u00a0", " ").strip()
    collapsed = "".join(text.split())
    if collapsed == "登录" and "企业" not in text and "微信" not in text:
      btn.click(timeout=8000)
      return
  # 兼容旧 NocoBase
  for locator in (
    page.get_by_role("button", name="action-Action-登录"),
    page.locator("button[type='submit']"),
  ):
    try:
      if locator.count() == 0:
        continue
      locator.first.click(timeout=8000)
      return
    except Exception:
      continue
  raise RuntimeError("登录页找不到可点击的密码登录按钮（请勿点企业微信登录）")


def _login(page) -> None:
  """兼容旧 NocoBase 与新站「登 录」；SPA 需等表单渲染。"""
  page.goto(LR_ADMIN_SIGNIN_URL, wait_until="domcontentloaded", timeout=120000)
  page.get_by_placeholder("密码").wait_for(state="visible", timeout=120000)
  if "/signin" not in page.url:
    return
  user = page.get_by_placeholder("用户名/邮箱")
  if user.count() == 0:
    user = page.get_by_placeholder("用户名")
  user.first.fill(ADMIN_USER)
  page.get_by_placeholder("密码").fill(ADMIN_PASSWORD)
  _click_password_login(page)
  page.wait_for_url(lambda u: "/signin" not in u, timeout=60000)


def _wait_admin_ready(page) -> None:
  page.goto(LR_ADMIN_URL, wait_until="domcontentloaded", timeout=120000)
  if "/signin" in page.url:
    _login(page)
    page.goto(LR_ADMIN_URL, wait_until="domcontentloaded", timeout=120000)
  for sel in (".ant-form-item", ".ant-table", "table", "text=区域", "text=日期"):
    try:
      page.locator(sel).first.wait_for(state="visible", timeout=20000)
      return
    except Exception:
      continue
  time.sleep(8)


def _set_region_filter(page, region: str) -> bool:
  """区域控件是 ant-input（非 select）。"""
  try:
    item = page.locator(".ant-form-item").filter(has_text="区域").first
    item.wait_for(state="visible", timeout=60000)
    inp = item.locator("input").first
    if inp.count() == 0:
      return False
    inp.click()
    inp.fill(region)
    time.sleep(0.4)
    opt = page.locator(".ant-select-item-option-content, [role=option]", has_text=region)
    if opt.count():
      opt.first.click()
    else:
      inp.press("Enter")
    time.sleep(0.8)
    return True
  except Exception:
    return False


def _set_date_filter(page, target: date) -> dict:
  """新站日期为 RangePicker（开始日期/结束日期）；旧站为相对词+指定日期。"""
  iso = target.isoformat()
  tried: list[dict] = []

  # 新站：开始日期 / 结束日期
  try:
    start = page.get_by_placeholder("开始日期")
    end = page.get_by_placeholder("结束日期")
    if start.count() and end.count():
      start.first.wait_for(state="visible", timeout=30000)
      start.first.click()
      start.first.fill(iso)
      end.first.click()
      end.first.fill(iso)
      end.first.press("Enter")
      time.sleep(0.4)
      page.keyboard.press("Escape")
      time.sleep(0.4)
      # 点空白处收起日历，避免 SCRAPE 扫到日历格子
      try:
        page.locator("text=LR日利润表数据").first.click(timeout=3000)
      except Exception:
        page.locator("body").click(position={"x": 8, "y": 8})
      time.sleep(1.0)
      sval = start.first.input_value()
      eval_ = end.first.input_value()
      ok = iso in (sval or "") and iso in (eval_ or "")
      tried.append({"value": f"range:{iso}", "ok": ok, "start": sval, "end": eval_})
      return {"ok": ok, "value": f"range:{iso}", "tried": tried}
  except Exception as exc:
    tried.append({"value": "range", "ok": False, "error": str(exc)})

  # 旧站：相对词 / 指定日期
  yesterday = date.today() - timedelta(days=1)
  today = date.today()
  try:
    date_item = page.locator(".ant-form-item").filter(has_text="日期").first
    date_item.wait_for(state="visible", timeout=60000)
    date_item.locator(".ant-select").first.click()
    time.sleep(0.5)
  except Exception as exc:
    return {"ok": False, "value": None, "tried": tried + [{"error": str(exc)}]}

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
      time.sleep(0.8)
      tried.append({"value": relative, "ok": True})
      return {"ok": True, "value": relative, "tried": tried}
    except Exception as exc:
      tried.append({"value": relative, "ok": False, "error": str(exc)})
      try:
        date_item.locator(".ant-select").first.click()
        time.sleep(0.4)
      except Exception:
        pass

  try:
    page.locator(
      ".ant-select-dropdown:not(.ant-select-dropdown-hidden) [role=option]",
      has_text="指定日期",
    ).first.click()
    time.sleep(0.8)
    picker = page.locator(".ant-picker input").first
    picker.click()
    picker.fill("")
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


def _api_list_fallback(page, target: date) -> dict | None:
  """登录后用 NocoBase token 直拉 list API（比 DOM 更稳）。"""
  try:
    token = page.evaluate(
      "() => localStorage.getItem('NOCOBASE_TOKEN') || localStorage.getItem('NOCOBASE_AUTH')"
    )
    if not token:
      return None
    # NOCOBASE_AUTH 可能是 JSON
    if token.startswith("{"):
      try:
        token = json.loads(token).get("token") or json.loads(token).get("data", {}).get("token")
      except Exception:
        pass
    if not token:
      return None

    iso = target.isoformat()
    parsed = urllib.parse.urlparse(LR_ADMIN_URL)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if "chuxin.city" not in origin:
      return None
    filt = {
      "$and": [
        {"日期": {"$dateOn": [iso, iso]}},
        {"区域": {"$includes": REGION_NAME}},
      ]
    }
    filter_q = urllib.parse.quote(
      json.dumps(filt, ensure_ascii=False, separators=(",", ":")),
      safe="",
    )
    url = (
      f"{origin}/api/t_w_dl:list?filter={filter_q}"
      f"&page=1&pageSize=200&tree=false"
      f"&sort[]=-%E6%97%A5%E6%9C%9F&sort[]=%E5%8C%BA%E5%9F%9F"
    )

    result = page.evaluate(
      """async ({ url, token }) => {
        const resp = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-Role': localStorage.getItem('NOCOBASE_ROLE') || 'admin',
          },
        });
        const text = await resp.text();
        let data = null;
        try { data = JSON.parse(text); } catch (e) { return { ok:false, status: resp.status, text: text.slice(0,300) }; }
        return { ok: resp.ok, status: resp.status, data };
      }""",
      {"url": url, "token": token},
    )
    if not result or not result.get("ok"):
      return None
    data = result.get("data") or {}
    rows_raw = data.get("data") or data.get("rows") or []
    if not isinstance(rows_raw, list) or not rows_raw:
      return None

    # 固定表头顺序（与页面一致）
    headers = [
      "区域", "城市", "日期", "原价交易额", "商品原价交易额", "餐盒费",
      "合作商补贴金额", "代补率", "全量订单量", "专送订单量(新)", "专送主板单量(新)",
      "专送拼好饭单量(新)", "众包主板单量(新)", "众包拼好饭单量(新)", "跑腿单量(新)",
      "高校订单", "HD活动花费", "商家服务费", "专送配送费", "后台收入",
    ]
    rows: list[list] = []
    for item in rows_raw:
      if not isinstance(item, dict):
        continue
      row = []
      for h in headers:
        v = item.get(h)
        if v is None:
          # 有时字段带空格
          for k, val in item.items():
            if str(k).strip() == h:
              v = val
              break
        if isinstance(v, (dict, list)):
          v = json.dumps(v, ensure_ascii=False)
        row.append("" if v is None else str(v))
      rows.append(row)
    if not rows:
      return None
    return {
      "headers": headers,
      "rows": rows,
      "table_count": 0,
      "body_snip": f"api:t_w_dl:list n={len(rows)}",
      "scraped_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
      "filters": {"region": REGION_NAME, "date": iso},
      "source": "api",
    }
  except Exception:
    return None


def scrape(out_path: Path | None = None, target_date: date | None = None) -> dict:
  from playwright.sync_api import sync_playwright

  target = target_date or (date.today() - timedelta(days=1))
  out_path = out_path or (LR_SCRAPE_DIR / "latest.json")
  out_path.parent.mkdir(parents=True, exist_ok=True)
  date_label = target.isoformat()

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1600, "height": 1200}, locale="zh-CN")
    page = context.new_page()

    _login(page)
    _wait_admin_ready(page)

    region_ok = _set_region_filter(page, REGION_NAME)
    date_info = _set_date_filter(page, target)

    payload: dict = {"headers": [], "rows": []}
    deadline = time.time() + 45
    while time.time() < deadline:
      time.sleep(2)
      payload = page.evaluate(SCRAPE_JS) or {}
      rows = payload.get("rows") or []
      # 至少看到目标日
      if any(date_label in (c or "") for r in rows for c in r):
        break

    # DOM 无数据或日期不对时，走 API
    rows = payload.get("rows") or []
    has_target = any(date_label in (c or "") for r in rows for c in r)
    if not rows or not has_target:
      api_payload = _api_list_fallback(page, target)
      if api_payload and api_payload.get("rows"):
        payload = api_payload

    payload["filter_apply"] = {
      "region_ok": region_ok,
      "date_ok": date_info["ok"],
      "date_value": date_info["value"],
      "date_tried": date_info["tried"],
    }
    payload["page_url"] = page.url
    payload["page_title"] = page.title()
    payload["target_date"] = date_label
    browser.close()

  if not payload.get("rows"):
    raise RuntimeError(
      "抓取到 0 行数据，"
      f"headers={payload.get('headers')} "
      f"tables={payload.get('table_count')} "
      f"url={payload.get('page_url')} "
      f"title={payload.get('page_title')!r} "
      f"filter={payload.get('filter_apply')} "
      f"body={payload.get('body_snip')!r}"
    )

  out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
      "source": payload.get("source", "dom"),
      "out": str(out),
    }, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
