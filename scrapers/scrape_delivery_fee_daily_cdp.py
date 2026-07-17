"""Power BI 配送费看板抓取：四块表（餐饮/非餐/餐饮KA/餐饮城商）明细+总计入库。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from scrapers._common import now, today, write_status
from scrapers.cdp_client import CDPError, connect_tab

POWERBI_URL = (
    "https://app.powerbi.com/reportEmbed"
    "?reportId=002a894f-ba61-4a4c-b99c-b275e5e4142f"
    "&autoAuth=true"
    "&ctid=7c792a97-2300-4444-aa97-172fed9b0501"
)
SECTIONS = ("餐饮", "非餐", "餐饮KA", "餐饮城商")


def _to_num(raw: str) -> float | None:
    s = (raw or "").strip().replace(",", "").replace("%", "")
    if not s or s in {"-", "--", "null", "None"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    return float(m.group(0))


def _extract_payload(session) -> dict:
    js = r"""
(() => {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const pickText = (root, sels) => {
    for (const sel of sels) {
      const n = root.querySelector(sel);
      if (n) {
        const t = norm(n.textContent || n.innerText || '');
        if (t) return t;
      }
    }
    return '';
  };

  const getContext = () => {
    const out = { area: '', city: '' };
    const labels = [...document.querySelectorAll('span,div,label')].map((x) => norm(x.textContent));
    for (let i = 0; i < labels.length; i++) {
      if (!out.area && labels[i] === '区域' && labels[i + 1]) out.area = labels[i + 1];
      if (!out.city && labels[i] === '城市' && labels[i + 1]) out.city = labels[i + 1];
    }
    return out;
  };

  const sections = ['餐饮', '非餐', '餐饮KA', '餐饮城商'];
  const visuals = [...document.querySelectorAll('.visual-container, .vcBody, section, div')];
  const tables = [];

  for (const root of visuals) {
    const title = pickText(root, [
      '.visual-title',
      '[class*="title"]',
      '[aria-label*="餐饮"]',
      '[aria-label*="非餐"]',
      'h2',
      'h3',
      'span'
    ]);
    const section = sections.find((s) => title && title.includes(s)) || '';
    if (!section) continue;

    let rows = [];
    let headers = [];

    const roleHeaders = [...root.querySelectorAll('[role="columnheader"]')].map((x) => norm(x.textContent));
    const roleRows = [...root.querySelectorAll('[role="row"]')];
    if (roleRows.length) {
      headers = roleHeaders;
      for (const r of roleRows) {
        const cells = [...r.querySelectorAll('[role="rowheader"],[role="gridcell"],[role="columnheader"]')]
          .map((c) => norm(c.textContent))
          .filter(Boolean);
        if (cells.length >= 2) rows.push(cells);
      }
    }

    if (!rows.length) {
      const table = root.querySelector('table');
      if (table) {
        headers = [...table.querySelectorAll('thead th')].map((x) => norm(x.textContent)).filter(Boolean);
        rows = [...table.querySelectorAll('tbody tr')]
          .map((tr) => [...tr.querySelectorAll('th,td')].map((td) => norm(td.textContent)).filter(Boolean))
          .filter((r) => r.length >= 2);
        if (!rows.length) {
          rows = [...table.querySelectorAll('tr')]
            .map((tr) => [...tr.querySelectorAll('th,td')].map((td) => norm(td.textContent)).filter(Boolean))
            .filter((r) => r.length >= 2);
        }
      }
    }

    if (rows.length) {
      tables.push({ section, title, headers, rows });
    }
  }

  const dedup = [];
  const seen = new Set();
  for (const t of tables) {
    const key = `${t.section}|${t.rows.length}|${(t.rows[0] || []).join('|')}`;
    if (seen.has(key)) continue;
    seen.add(key);
    dedup.push(t);
  }
  return { context: getContext(), tables: dedup };
})()
"""
    return session.evaluate(js, await_promise=False) or {}


def _save_rows(payload: dict) -> int:
    ts = now()
    d = today()
    ctx = payload.get("context") or {}
    city = (ctx.get("city") or "").strip() or None
    area = (ctx.get("area") or "").strip() or None
    rows = []
    for t in payload.get("tables") or []:
        section = (t.get("section") or "").strip()
        headers = [h.strip() for h in (t.get("headers") or [])]
        for r in t.get("rows") or []:
            if len(r) < 2:
                continue
            row_name = (r[0] or "").strip()
            if not row_name:
                continue
            is_total = 1 if row_name in {"总计", "合计"} else 0
            for i, cell in enumerate(r[1:], start=1):
                metric_key = headers[i] if i < len(headers) and headers[i] else f"col_{i}"
                rows.append(
                    (
                        d,
                        city,
                        area,
                        section,
                        row_name,
                        metric_key,
                        cell,
                        _to_num(cell),
                        is_total,
                        json.dumps({"title": t.get("title"), "headers": headers, "raw_row": r}, ensure_ascii=False),
                        ts,
                    )
                )
    return db.upsert_many(
        """INSERT OR REPLACE INTO powerbi_delivery_rows
           (snapshot_date, city, area, section, row_name, metric_key, metric_text, metric_value, is_total, detail_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def main() -> int:
    db.init_db()
    try:
        session = connect_tab(9222, ["app.powerbi.com", "reportEmbed"])
    except CDPError as exc:
        db.log_sync("scrape_delivery_fee_daily_cdp", "fail", str(exc))
        write_status("scrape_delivery_fee_daily_cdp", {"ok": False, "error": str(exc)})
        print(exc)
        return 1

    try:
        session.navigate(POWERBI_URL, wait_sec=8.0)
        payload = {}
        for _ in range(4):
            payload = _extract_payload(session)
            tables = payload.get("tables") if isinstance(payload, dict) else None
            if tables:
                break
            time.sleep(2)

        if not payload or not payload.get("tables"):
            msg = "未抓到 Power BI 表格，请确认页面已完成渲染并处于目标报表。"
            db.log_sync("scrape_delivery_fee_daily_cdp", "fail", msg)
            write_status("scrape_delivery_fee_daily_cdp", {"ok": False, "message": msg, "payload": payload})
            print(msg)
            return 1

        n = _save_rows(payload)
        ctx = payload.get("context") or {}
        msg = f"Power BI 抓取成功：{len(payload.get('tables', []))} 个表，写入 {n} 条（城市={ctx.get('city') or '未知'}）"
        db.log_sync("scrape_delivery_fee_daily_cdp", "ok", msg)
        write_status("scrape_delivery_fee_daily_cdp", {"ok": True, "rows": n, "context": ctx, "tables": payload.get("tables")})
        print(msg)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
