"""业务数据风向看板：抓取「城市数据」表中的在线商家数等指标（CDP evaluate 用）。"""
from __future__ import annotations

POWERBI_WIND_HELPERS_JS = r"""
(() => {
  if (window.__CZ_PBI_WIND) return window.__CZ_PBI_WIND;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();

  function findVisual(title) {
    const h = [...document.querySelectorAll('h3')].find((x) => norm(x.textContent) === title);
    return h ? h.closest('.visualContainer') || h.parentElement?.parentElement : null;
  }

  function pageDateRaw() {
    const el = [...document.querySelectorAll('div,span')].find(
      (e) => /数据更新至/.test(norm(e.textContent)) || /^\d{4}\/\d{1,2}\/\d{1,2}$/.test(norm(e.textContent))
    );
    if (!el) return null;
    const m = norm(el.textContent).match(/(\d{4}\/\d{1,2}\/\d{1,2})/);
    return m ? m[1] : norm(el.textContent);
  }

  function pageDateISO() {
    const raw = pageDateRaw();
    if (!raw) return null;
    const m = raw.match(/(\d{4})\/(\d{1,2})\/(\d{1,2})/);
    if (!m) return null;
    return `${m[1]}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`;
  }

  async function openSlicer(title) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(200);
    const visual = findVisual(title);
    if (!visual) return { ok: false, err: 'no visual', title };
    const combo = visual.querySelector('[role="combobox"]');
    if (!combo) return { ok: false, err: 'no combo', title };
    combo.click();
    await sleep(700);
    return { ok: true, visual, combo };
  }

  function visibleSlicerItems() {
    return [...document.querySelectorAll('.slicerItemContainer')].filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
  }

  async function selectSlicerValue(title, value, { clear = true } = {}) {
    const opened = await openSlicer(title);
    if (!opened.ok) return opened;
    const visual = opened.visual;
    if (clear) {
      const clearBtn = [...visual.querySelectorAll('button')].find((b) =>
        /清除/.test(norm(b.getAttribute('aria-label') || b.textContent || ''))
      );
      if (clearBtn) {
        clearBtn.click();
        await sleep(600);
        opened.combo.click();
        await sleep(600);
      }
    }
    const want = String(value);
    for (let i = 0; i < 60; i++) {
      const hit = visibleSlicerItems().find((el) => {
        const t = norm(el.querySelector('.slicerText')?.textContent || el.getAttribute('title') || '');
        return t === want;
      });
      if (hit) {
        (hit.querySelector('input[type="checkbox"]') || hit).click();
        await sleep(900);
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        await sleep(300);
        return { ok: true, title, value: want };
      }
      await sleep(80);
    }
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return { ok: false, err: 'not found', title, value: want };
  }

  async function ensureLatestDate() {
    return selectSlicerValue('最新日期', '是', { clear: true });
  }

  async function ensureArea(area = '川藏一区') {
    const text = norm(findVisual('区域')?.innerText || '');
    if (text.includes(area)) return { ok: true, text };
    return selectSlicerValue('区域', area, { clear: true });
  }

  async function ensureCatering() {
    const text = norm(findVisual('餐饮')?.innerText || findVisual('行业')?.innerText || '');
    if (text.includes('餐饮')) return { ok: true, text };
    for (const title of ['餐饮', '行业', '品类']) {
      const r = await selectSlicerValue(title, '餐饮', { clear: true });
      if (r.ok) return r;
    }
    return { ok: false, err: 'catering slicer not found' };
  }

  async function selectMetric(name) {
    for (const title of ['指标', '度量', '在线商家数']) {
      const r = await selectSlicerValue(title, name, { clear: true });
      if (r.ok) return r;
    }
    return { ok: false, err: 'metric slicer not found', name };
  }

  function readCityTable() {
    const visual = findVisual('城市数据');
    if (!visual) return { headers: [], rows: [] };
    const headers = [...visual.querySelectorAll('[role="columnheader"]')]
      .map((x) => norm(x.textContent)).filter(Boolean);
    const rows = [];
    for (const r of visual.querySelectorAll('[role="row"]')) {
      const cells = [...r.querySelectorAll('[role="rowheader"],[role="gridcell"]')]
        .map((c) => norm(c.textContent)).filter((x) => x !== '');
      if (cells.length >= 2) rows.push(cells);
    }
    return { headers, rows };
  }

  async function scrapeOnlineMerchants() {
    await ensureLatestDate();
    await ensureArea('川藏一区');
    await ensureCatering();
    await selectMetric('在线商家数');
    await sleep(1500);
    const table = readCityTable();
    const cities = {};
    const metricCol = table.headers.find((h) => /在线商家/.test(h)) || table.headers[table.headers.length - 1];
    const cityCol = table.headers.find((h) => /城市/.test(h)) || table.headers[0];
    const mi = table.headers.indexOf(metricCol);
    const ci = table.headers.indexOf(cityCol);
    for (const row of table.rows) {
      const city = row[ci >= 0 ? ci : 0];
      const valRaw = row[mi >= 0 ? mi : row.length - 1];
      if (!city || city === '总计' || city === '城市') continue;
      const num = parseInt(String(valRaw).replace(/,/g, ''), 10);
      if (!Number.isNaN(num)) cities[city] = num;
    }
    return {
      ok: true,
      date: pageDateISO(),
      date_raw: pageDateRaw(),
      metric: '在线商家数',
      filters: { 区域: '川藏一区', 餐饮: '餐饮' },
      headers: table.headers,
      rows: table.rows,
      cities,
    };
  }

  window.__CZ_PBI_WIND = {
    sleep, norm, findVisual, pageDateISO, pageDateRaw,
    selectSlicerValue, ensureLatestDate, ensureArea, ensureCatering, selectMetric,
    readCityTable, scrapeOnlineMerchants,
  };
  return window.__CZ_PBI_WIND;
})()
"""
