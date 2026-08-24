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


def _click_first(page, selectors: list[str]) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() == 0:
                continue
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    item.click(timeout=5000)
                    return True
        except Exception:
            continue
    return False


def _wait_new_xlsx(out_dir: Path, since: float, timeout_s: float = 180) -> Path | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cands = []
        for p in out_dir.glob("*.xlsx"):
            try:
                if p.stat().st_mtime >= since and p.stat().st_size > 100:
                    cands.append(p)
            except OSError:
                continue
        # also Chromium temp *.crdownload finishing
        if cands:
            return max(cands, key=lambda p: p.stat().st_mtime)
        time.sleep(1)
    return None


def scrape_export(out_dir: Path | None = None) -> Path:
    from playwright.sync_api import sync_playwright

    out_dir = out_dir or VISIT_EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = ROOT / "logs"
    debug_dir.mkdir(parents=True, exist_ok=True)
    since = time.time() - 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1200},
            accept_downloads=True,
        )
        page = context.new_page()

        # Force downloads into out_dir (more reliable than only expect_download)
        try:
            client = context.new_cdp_session(page)
            client.send(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(out_dir.resolve())},
            )
        except Exception:
            pass

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

        # Wait for table rows
        time.sleep(60)
        try:
            page.wait_for_selector("tbody tr", timeout=60000)
        except Exception:
            pass
        time.sleep(30)

        # Click export (toolbar)
        export_clicked = _click_first(
            page,
            [
                "button:has-text('导出')",
                "[aria-label*='导出']",
                ".ant-btn:has-text('导出')",
                "text=导出",
            ],
        )
        if not export_clicked:
            page.screenshot(path=str(debug_dir / "visit_export_no_btn.png"), full_page=True)
            raise RuntimeError("未找到「导出」按钮，见 logs/visit_export_no_btn.png")

        time.sleep(1.5)

        # Confirm in modal — this is usually what triggers the download
        confirm_clicked = _click_first(
            page,
            [
                ".ant-modal-confirm button.ant-btn-primary",
                ".ant-modal button.ant-btn-primary:has-text('确定')",
                ".ant-modal button:has-text('确定')",
                ".ant-popover button:has-text('确定')",
                "button.ant-btn-primary:has-text('确定')",
                "button:has-text('确定')",
                "button:has-text('OK')",
            ],
        )

        dest: Path | None = None
        # Strategy A: Playwright download event
        try:
            with page.expect_download(timeout=30000) as download_info:
                if not confirm_clicked:
                    # maybe first click already triggered download; no-op click fallback
                    _click_first(page, ["button:has-text('导出')"])
            download = download_info.value
            dest = out_dir / (download.suggested_filename or "visit_export.xlsx")
            if not str(dest).lower().endswith((".xlsx", ".xls", ".xlsm")):
                dest = out_dir / "visit_export.xlsx"
            download.save_as(str(dest))
        except Exception:
            # Strategy B: poll CDP download folder
            dest = _wait_new_xlsx(out_dir, since=since, timeout_s=150)

        if dest is None or not dest.exists() or dest.stat().st_size < 100:
            page.screenshot(path=str(debug_dir / "visit_export_timeout.png"), full_page=True)
            browser.close()
            raise RuntimeError(
                "导出超时：未收到 Excel 下载。"
                f" region_ok={region_ok} date_ok={date_ok} confirm={confirm_clicked}。"
                "见 logs/visit_export_timeout.png"
            )

        browser.close()

    meta = {
        "ok": True,
        "path": str(dest),
        "bytes": dest.stat().st_size,
        "filter_apply": {"region_ok": region_ok, "date_ok": date_ok, "confirm_clicked": confirm_clicked},
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
