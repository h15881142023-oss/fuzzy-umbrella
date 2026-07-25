#!/usr/bin/env python3
"""代补看板日更：页面日期为准、历史不覆盖、缺日补齐、等到 t-1 再抓。

流程：
1. 连接已登录的 Power BI Chrome（CDP 9222）
2. 刷新页面，确保「最新日期=是」「区域=川藏一区」
3. 若页面日期 < 昨天(t-1)：每 10 分钟刷新一次，直到页面日期 == t-1（一直等到出数）
4. 计算缺日：从库内最早日期到页面日期，任一城缺失则列入
5. 对每个缺日：切到该日 → 五城四块表抓取 → 入库（已存在跳过）

用法：
  bash scripts/start_chrome_powerbi.sh   # 若尚未开 CDP
  python scrapers/powerbi_subsidy_daily.py
  python scrapers/powerbi_subsidy_daily.py --once   # 只跑一轮，不等待
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from config import CITIES
from scrapers._common import now, write_status
from scrapers.cdp_client import CDPError, connect_tab
from scrapers.import_powerbi_browser import city_date_exists, import_payload, parse_page_date
from scrapers.powerbi_page_js import POWERBI_HELPERS_JS

POWERBI_URL = (
    "https://app.powerbi.com/reportEmbed"
    "?reportId=002a894f-ba61-4a4c-b99c-b275e5e4142f"
    "&autoAuth=true"
    "&ctid=7c792a97-2300-4444-aa97-172fed9b0501"
)
POLL_SEC = 10 * 60
AREA = "川藏一区"


def _log(msg: str) -> None:
    print(f"[powerbi_daily {now()}] {msg}", flush=True)


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _inject(session) -> None:
    session.evaluate(POWERBI_HELPERS_JS, await_promise=False, timeout=30)


def _probe_page(session) -> dict:
    """探测当前页是否已进入报表（避免 body 里「登录/验证」误判）。"""
    try:
        info = session.evaluate(
            """(() => {
              const href = location.href || '';
              const host = (location.hostname || '').toLowerCase();
              const title = document.title || '';
              const text = (document.body && document.body.innerText || '').slice(0, 1200);
              const hasSubsidyTab = [...document.querySelectorAll('button,[role="tab"]')]
                .some((el) => ((el.textContent || '').replace(/\\s+/g, ' ').trim()) === '补贴监测');
              const hasSlicer = !!document.querySelector('.slicerItemContainer, .slicer-dropdown-menu, [aria-label*="区域"]');
              const hasVisual = !!document.querySelector('.visualContainer, .visual-container');
              const hasPageDate = /\\d{4}\\/\\d{1,2}\\/\\d{1,2}/.test(text);
              const reportReady = hasSubsidyTab || hasSlicer || hasVisual || hasPageDate;

              const loginHost =
                /(^|\\.)login\\.microsoftonline\\.com$|(^|\\.)login\\.live\\.com$|(^|\\.)account\\.microsoft\\.com$|(^|\\.)login\\.windows\\.net$/i.test(host);
              const loginPath =
                /\\/(common|organizations|consumers)\\/oauth2\\//i.test(href) ||
                /[?&#]wa=wsignin/i.test(href);
              const titleLooksLogin = /sign\\s*in|log\\s*in|登录|登陆/i.test(title);
              // 仅看标题/真实登录域，不扫 body：报表文案常含「验证/登录」导致误判
              const onLoginPage = loginHost || loginPath || (titleLooksLogin && !reportReady && !/powerbi\\.com/i.test(host));

              return {
                href, host, title, reportReady, onLoginPage,
                hasSubsidyTab, hasSlicer, hasVisual, hasPageDate,
              };
            })()""",
            await_promise=False,
            timeout=20,
        ) or {}
        return info
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "reportReady": False, "onLoginPage": False}


def _login_hint(session) -> str | None:
    info = _probe_page(session)
    if info.get("error"):
        return f"page_probe_fail: {info['error']}"
    if info.get("reportReady"):
        return None
    if info.get("onLoginPage"):
        return f"Power BI 似乎未登录或停在登录页: {info.get('href')}"
    return None


def _wait_report_ready(session, *, timeout_sec: float = 90.0) -> dict:
    """navigate/autoAuth 后等待报表控件出现；仅在确认登录页时提前失败。"""
    deadline = time.time() + timeout_sec
    last: dict = {}
    while time.time() < deadline:
        last = _probe_page(session)
        if last.get("reportReady"):
            return last
        if last.get("onLoginPage"):
            raise RuntimeError(
                f"Power BI 似乎未登录或停在登录页: {last.get('href')}；"
                "请在 ChromeAutomation 窗口完成登录后保持窗口开启再重跑"
            )
        time.sleep(2.5)
    # 超时仍未 ready：若仍在 powerbi 报表域，交给后续 prepare（可能是加载慢）
    href = str(last.get("href") or "")
    if "powerbi.com" in href and "reportEmbed" in href and not last.get("onLoginPage"):
        _log(f"报表控件等待超时，继续尝试 prepare: {last}")
        return last
    raise RuntimeError(
        f"Power BI 报表未就绪: href={last.get('href')} title={last.get('title')!r} "
        f"probe={ {k: last.get(k) for k in ('hasSubsidyTab','hasSlicer','hasVisual','hasPageDate','onLoginPage')} }"
    )


def _status(session) -> dict:
    _inject(session)
    return session.evaluate("window.__CZ_PBI.status()", await_promise=False, timeout=30) or {}


def _page_date(session) -> date | None:
    st = _status(session)
    iso = parse_page_date(st.get("page_date") or st.get("page_date_raw"))
    if not iso:
        return None
    return date.fromisoformat(iso)


def _goto_subsidy_tab(session) -> None:
    _inject(session)
    session.evaluate(
        """(() => {
          const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const tab = [...document.querySelectorAll('button,[role=\"tab\"]')]
            .find((el) => norm(el.textContent) === '补贴监测');
          if (tab) tab.click();
          return !!tab;
        })()""",
        await_promise=False,
        timeout=30,
    )
    time.sleep(3)


def _reload(session, wait: float = 8.0) -> None:
    session.reload(wait_sec=wait)
    _inject(session)
    _goto_subsidy_tab(session)
    time.sleep(2)


def _prepare_latest(session) -> dict:
    _wait_report_ready(session, timeout_sec=45)
    hint = _login_hint(session)
    if hint:
        raise RuntimeError(hint + "；请在 ChromeAutomation 窗口登录后重跑")
    _inject(session)
    # 等切片器渲染
    time.sleep(3)
    area = session.evaluate(
        f"window.__CZ_PBI.ensureArea({AREA!r})",
        await_promise=True,
        timeout=90,
    )
    latest = session.evaluate(
        "window.__CZ_PBI.setLatestDateMode(true)",
        await_promise=True,
        timeout=90,
    )
    time.sleep(2)
    return {"area": area, "latest": latest, "status": _status(session)}

def _missing_dates(page_d: date) -> list[date]:
    """从库内最早日期到 page_d，凡缺任一标准城的日期都要补。"""
    rows = db.query_all("SELECT DISTINCT snapshot_date FROM powerbi_delivery_rows ORDER BY snapshot_date")
    existing_dates = [date.fromisoformat(r["snapshot_date"]) for r in rows if r.get("snapshot_date")]
    if existing_dates:
        start = min(existing_dates)
    else:
        start = page_d

    out: list[date] = []
    cur = start
    while cur <= page_d:
        for city in CITIES:
            if not city_date_exists(cur.isoformat(), city):
                out.append(cur)
                break
        cur += timedelta(days=1)
    return out


def _select_date(session, d: date, use_latest: bool) -> bool:
    _inject(session)
    if use_latest:
        session.evaluate("window.__CZ_PBI.setLatestDateMode(true)", await_promise=True)
        time.sleep(2)
        got = _page_date(session)
        return got == d
    res = session.evaluate(
        f"window.__CZ_PBI.selectCalendarDate({d.isoformat()!r})",
        await_promise=True,
    )
    _log(f"切日期 {d}: {res}")
    got = _page_date(session)
    return got == d


def _scrape_city(session, city: str) -> dict:
    _inject(session)
    return session.evaluate(f"window.__CZ_PBI.scrapeCity({city!r})", await_promise=True) or {}


def _import_city(payload: dict, snapshot: str) -> dict:
    payload = dict(payload)
    payload["page_date"] = snapshot
    payload["area"] = AREA
    return import_payload(payload, snapshot_date=snapshot, overwrite=False)


def scrape_date(session, d: date, *, use_latest: bool) -> dict:
    iso = d.isoformat()
    need = [c for c in CITIES if not city_date_exists(iso, c)]
    if not need:
        return {"ok": True, "date": iso, "skipped": "all_exist", "results": []}

    if not _select_date(session, d, use_latest=use_latest):
        got = _page_date(session)
        return {"ok": False, "date": iso, "error": f"页面日期未切到 {iso}，当前={got}"}

    session.evaluate(f"window.__CZ_PBI.ensureArea({AREA!r})", await_promise=True)
    results = []
    for city in need:
        _log(f"抓取 {iso} / {city}")
        payload = _scrape_city(session, city)
        if not payload.get("ok"):
            results.append({"city": city, "ok": False, "payload": payload})
            continue
        # 强制用目标业务日，避免切城后页面抖动
        payload["page_date"] = iso
        imp = _import_city(payload, iso)
        results.append({"city": city, "ok": True, "import": imp})
        _log(f"入库 {city}: {imp}")
    return {"ok": all(r.get("ok") for r in results), "date": iso, "results": results}


def wait_until_t1(session, *, once: bool) -> date:
    """刷新并等到页面日期 == 昨天。"""
    target = _yesterday()
    while True:
        _reload(session, wait=12)
        prep = None
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                prep = _prepare_latest(session)
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                _log(f"prepare_latest 失败({attempt}/3): {exc}")
                time.sleep(3)
                _reload(session, wait=10)
        if last_err is not None:
            if once:
                raise SystemExit(f"prepare_latest 失败: {last_err}")
            _log(f"prepare 连续失败，{POLL_SEC // 60} 分钟后重试…")
            time.sleep(POLL_SEC)
            continue

        page_d = _page_date(session)
        if page_d is None:
            # 切片器刚切完时日期可能尚未渲染，多等几轮
            for _ in range(6):
                time.sleep(2)
                page_d = _page_date(session)
                if page_d is not None:
                    break
        _log(f"页面日期={page_d} 目标t-1={target} prep={prep.get('status') if prep else None}")
        if page_d and page_d >= target:
            if page_d > target:
                _log(f"警告：页面日期 {page_d} 晚于 t-1 {target}，仍按页面日期抓取")
            return page_d
        if once:
            raise SystemExit(f"尚未到 t-1：页面={page_d} 目标={target}")
        _log(f"未到 t-1，{POLL_SEC // 60} 分钟后刷新重试…")
        time.sleep(POLL_SEC)


def run(*, once: bool = False) -> int:
    db.init_db()
    try:
        session = connect_tab(9222, ["app.powerbi.com", "reportEmbed", "powerbi.com"])
    except CDPError as exc:
        db.log_sync("powerbi_subsidy_daily", "fail", str(exc))
        write_status("powerbi_subsidy_daily", {"ok": False, "error": str(exc)})
        _log(str(exc))
        return 1

    try:
        session.navigate(POWERBI_URL, wait_sec=18)
        try:
            probe = _wait_report_ready(session, timeout_sec=90)
            _log(f"报表探测: { {k: probe.get(k) for k in ('hasSubsidyTab','hasSlicer','hasVisual','hasPageDate','onLoginPage')} }")
        except RuntimeError as exc:
            hint = str(exc)
            _log(hint)
            db.log_sync("powerbi_subsidy_daily", "fail", hint)
            write_status("powerbi_subsidy_daily", {"ok": False, "error": hint})
            return 1
        _goto_subsidy_tab(session)
        page_d = wait_until_t1(session, once=once)
        missing = _missing_dates(page_d)
        _log(f"缺日列表: {[x.isoformat() for x in missing]}")

        all_results = []
        for d in missing:
            use_latest = d == page_d
            # 最新日用「最新日期=是」；历史缺日用年月日点选
            res = scrape_date(session, d, use_latest=use_latest)
            all_results.append(res)
            if not res.get("ok") and not use_latest:
                # 历史切日失败时再尝试一次：刷新后重切
                _log(f"切日失败重试: {d}")
                _reload(session, wait=8)
                _prepare_latest(session)
                res2 = scrape_date(session, d, use_latest=False)
                all_results[-1] = res2

        # 回到最新日期模式，方便下次
        try:
            _prepare_latest(session)
        except Exception:
            pass

        ok = all(r.get("ok") for r in all_results) if all_results else True
        summary = {
            "ok": ok,
            "page_date": page_d.isoformat(),
            "missing": [d.isoformat() for d in missing],
            "results": all_results,
            "finished_at": now(),
        }
        write_status("powerbi_subsidy_daily", summary)
        db.log_sync(
            "powerbi_subsidy_daily",
            "ok" if ok else "fail",
            f"page={page_d} missing={len(missing)} ok={ok}",
        )
        _log(f"完成 ok={ok} page={page_d} missing={len(missing)}")
        return 0 if ok else 2
    finally:
        session.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="不等待轮询，只跑当前一轮")
    args = ap.parse_args()
    return run(once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
