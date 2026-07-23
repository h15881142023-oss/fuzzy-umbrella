#!/usr/bin/env python3
"""本机：登录后台，筛选川藏一区+昨天，导出拜访 Excel 到 data/visit_exports/。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ADMIN_SIGNIN_URL,
    ADMIN_USER,
    REGION_NAME,
    VISIT_ADMIN_URL,
    VISIT_EXPORT_DIR,
)


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


def scrape_export(out_dir: Path | None = None) -> Path:
  from playwright.sync_api import sync_playwright

  out_dir = out_dir or VISIT_EXPORT_DIR
  out_dir.mkdir(parents=True, exist_ok=True)

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
      viewport={"width": 1600, "height": 1200},
      accept_downloads=True,
    )
    page = context.new_page()

    page.goto(ADMIN_SIGNIN_URL, wait_until="networkidle", timeout=120000)
    if "/signin" in page.url:
      page.get_by_placeholder("用户名/邮箱").fill(ADMIN_USER)
      page.get_by_placeholder("密码").fill(ADMIN_PASSWORD)
      page.get_by_role("button", name="action-Action-登录").click()
      page.wait_for_url(lambda u: "/signin" not in u, timeout=60000)

    page.goto(VISIT_ADMIN_URL, wait_until="networkidle", timeout=120000)
    time.sleep(3)

    region_ok = _set_filter_by_label(page, "区域", REGION_NAME)
    date_ok = _set_filter_by_label(page, "拜访时间", "昨天")
    if not date_ok:
      date_ok = _set_filter_by_label(page, "时间", "昨天")

    # 等待表格刷新
    time.sleep(90)

    # 点击导出
    export_btn = page.get_by_role("button", name="导出")
    if export_btn.count() == 0:
      export_btn = page.locator("button:has-text('导出')")
    if export_btn.count() == 0:
      raise RuntimeError("未找到「导出」按钮")

    with page.expect_download(timeout=180000) as download_info:
      export_btn.first.click()
      # 确认对话框
      confirm = page.get_by_role("button", name="确定")
      if confirm.count() == 0:
        confirm = page.locator("button:has-text('确定')")
      if confirm.count() > 0:
        confirm.first.click()

    download = download_info.value
    dest = out_dir / (download.suggested_filename or "visit_export.xlsx")
    if not dest.suffix.lower().startswith(".xls"):
      dest = out_dir / "visit_export.xlsx"
    download.save_as(str(dest))
    browser.close()

  if not dest.exists() or dest.stat().st_size < 100:
    raise RuntimeError(f"导出文件无效: {dest}")

  meta = {
    "ok": True,
    "path": str(dest),
    "bytes": dest.stat().st_size,
    "filter_apply": {"region_ok": region_ok, "date_ok": date_ok},
  }
  print(json.dumps(meta, ensure_ascii=False, indent=2))
  return dest


def main() -> int:
  try:
    scrape_export()
    return 0
  except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
