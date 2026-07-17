"""Power BI 代补看板：页面日期解析、筛选切换、四块表滚动抓取（CDP evaluate 用）。"""
from __future__ import annotations

# 在浏览器内执行的 JS 工具集（通过 session.evaluate 注入）
POWERBI_HELPERS_JS = r"""
(() => {
  if (window.__CZ_PBI) return window.__CZ_PBI;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();

  function findVisual(title) {
    const h = [...document.querySelectorAll('h3')].find((x) => norm(x.textContent) === title);
    return h ? h.closest('.visualContainer') || h.parentElement.parentElement : null;
  }

  function pageDateRaw() {
    const el = [...document.querySelectorAll('div,span')].find(
      (e) => /^\d{4}\/\d{1,2}\/\d{1,2}$/.test(norm(e.textContent)) && e.children.length === 0
    );
    return el ? norm(el.textContent) : null;
  }

  function pageDateISO() {
    const raw = pageDateRaw();
    if (!raw) return null;
    const m = raw.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
    if (!m) return null;
    return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
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
    const search = document.querySelector(
      'input.searchInput, .searchHeader input, .slicer-dropdown-menu input'
    );
    if (search) {
      search.focus();
      search.value = want;
      search.dispatchEvent(new Event('input', { bubbles: true }));
      await sleep(350);
    }

    for (let i = 0; i < 60; i++) {
      const hit = visibleSlicerItems().find((el) => {
        const t = norm(el.querySelector('.slicerText')?.textContent || el.getAttribute('title') || '');
        return t === want;
      });
      if (hit) {
        (hit.querySelector('input[type="checkbox"]') || hit).click();
        await sleep(1100);
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        await sleep(300);
        return { ok: true, title, value: want, text: norm(visual.innerText).slice(0, 80) };
      }
      const any = document.querySelector('.slicerItemContainer');
      let sc = any;
      while (sc && sc !== document.body) {
        if (sc.scrollHeight > sc.clientHeight + 5) break;
        sc = sc.parentElement;
      }
      if (sc && sc !== document.body) sc.scrollTop = Math.min(sc.scrollTop + 100, sc.scrollHeight);
      await sleep(60);
    }
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return { ok: false, err: 'not found', title, value: want };
  }

  async function ensureArea(area = '川藏一区') {
    const text = norm(findVisual('区域')?.innerText || '');
    if (text.includes(area)) return { ok: true, text };
    return selectSlicerValue('区域', area, { clear: true });
  }

  async function selectCity(city) {
    return selectSlicerValue('城市', city, { clear: true });
  }

  async function setLatestDateMode(yes) {
    return selectSlicerValue('最新日期', yes ? '是' : '否', { clear: true });
  }

  async function selectCalendarDate(iso) {
    // iso: YYYY-MM-DD
    const [y, m, d] = iso.split('-');
    const monthNum = String(Number(m));
    const dayNum = String(Number(d));
    const r0 = await setLatestDateMode(false);
    if (!r0.ok) return { ok: false, step: 'latest', detail: r0 };
    const r1 = await selectSlicerValue('年', y, { clear: true });
    if (!r1.ok) return { ok: false, step: 'year', detail: r1 };
    const r2 = await selectSlicerValue('月', monthNum, { clear: true });
    if (!r2.ok) return { ok: false, step: 'month', detail: r2 };
    await sleep(800);
    const r3 = await selectSlicerValue('日', dayNum, { clear: true });
    if (!r3.ok) return { ok: false, step: 'day', detail: r3 };
    await sleep(1500);
    const got = pageDateISO();
    return { ok: got === iso, wanted: iso, got, r0, r1, r2, r3 };
  }

  function readRows(visual) {
    const headers = [...visual.querySelectorAll('[role="columnheader"]')]
      .map((x) => norm(x.textContent))
      .filter(Boolean);
    const rows = [];
    for (const r of visual.querySelectorAll('[role="row"]')) {
      const cells = [...r.querySelectorAll('[role="rowheader"],[role="gridcell"],[role="columnheader"]')]
        .map((c) => norm(c.textContent))
        .filter(Boolean);
      if (cells.length >= 2) rows.push(cells);
    }
    return { headers, rows };
  }

  async function scrapeSection(sec) {
    const visual = findVisual(sec);
    if (!visual) return { section: sec, headers: [], rows: [] };
    const up = [...visual.querySelectorAll('button')].find((b) =>
      /向上滚动/.test(norm(b.getAttribute('aria-label') || b.textContent || ''))
    );
    const down = [...visual.querySelectorAll('button')].find((b) =>
      /向下滚动/.test(norm(b.getAttribute('aria-label') || b.textContent || ''))
    );
    for (let i = 0; i < 25; i++) {
      if (up) up.click();
      await sleep(30);
    }
    await sleep(180);
    const seen = new Set();
    const all = [];
    let headers = [];
    const absorb = () => {
      const data = readRows(visual);
      if (data.headers.length) headers = data.headers;
      for (const r of data.rows) {
        if (r[0] === '行选择' && r[1] === '活动大类') continue;
        const key = r.join('|');
        if (seen.has(key)) continue;
        seen.add(key);
        all.push(r);
      }
    };
    absorb();
    for (let i = 0; i < 40; i++) {
      if (down) down.click();
      await sleep(80);
      absorb();
      if (all.some((r) => r[0] === '总计')) {
        for (let j = 0; j < 2; j++) {
          if (down) down.click();
          await sleep(70);
          absorb();
        }
        break;
      }
    }
    return { section: sec, headers, rows: all };
  }

  async function scrapeAllSections() {
    const sections = [];
    for (const sec of ['餐饮', '非餐', '餐饮KA', '餐饮城商']) {
      sections.push(await scrapeSection(sec));
    }
    return sections;
  }

  async function scrapeCity(city) {
    const sel = await selectCity(city);
    if (!sel.ok) return { ok: false, city, select: sel };
    await sleep(1200);
    const sections = await scrapeAllSections();
    return {
      ok: true,
      area: '川藏一区',
      city,
      page_date: pageDateISO(),
      page_date_raw: pageDateRaw(),
      filters: {
        area: norm(findVisual('区域')?.innerText || ''),
        city: norm(findVisual('城市')?.innerText || ''),
        latest: norm(findVisual('最新日期')?.innerText || ''),
      },
      sections,
      select: sel,
    };
  }

  window.__CZ_PBI = {
    sleep,
    norm,
    findVisual,
    pageDateRaw,
    pageDateISO,
    selectSlicerValue,
    ensureArea,
    selectCity,
    setLatestDateMode,
    selectCalendarDate,
    scrapeAllSections,
    scrapeCity,
    status: () => ({
      page_date: pageDateISO(),
      page_date_raw: pageDateRaw(),
      area: norm(findVisual('区域')?.innerText || ''),
      city: norm(findVisual('城市')?.innerText || ''),
      latest: norm(findVisual('最新日期')?.innerText || ''),
      year: norm(findVisual('年')?.innerText || ''),
      month: norm(findVisual('月')?.innerText || ''),
      day: norm(findVisual('日')?.innerText || ''),
    }),
  };
  return window.__CZ_PBI;
})()
"""
