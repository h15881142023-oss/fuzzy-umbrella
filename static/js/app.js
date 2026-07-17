async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("unauthorized");
  }
  return res.json();
}

function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    return Number.isInteger(v) ? String(v) : v.toFixed(2);
  }
  return String(v);
}

function pct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return `${(Number(v) * 100).toFixed(1)}%`;
}

function renderTable(el, columns, rows) {
  if (!el) return;
  if (!rows || !rows.length) {
    el.innerHTML = '<div class="empty">暂无数据。可将 Excel 拖入桌面「川藏一区数据更新」对应文件夹，或点击右上角同步。</div>';
    return;
  }
  const thead = `<tr>${columns.map((c) => `<th>${c.label}</th>`).join("")}</tr>`;
  const tbody = rows
    .map((row) => {
      const tds = columns
        .map((c) => {
          const raw = row[c.key];
          const val = c.format ? c.format(raw, row) : fmt(raw);
          return `<td>${val}</td>`;
        })
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  el.innerHTML = `<table class="data"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
}

async function loadTable({ endpoint, mount, columns, statusEl }) {
  if (statusEl) statusEl.textContent = "加载中…";
  try {
    const json = await fetchJson(endpoint);
    const rows = json.data || json.daily || [];
    renderTable(mount, columns, rows);
    if (statusEl) statusEl.textContent = `共 ${rows.length} 条`;
    return json;
  } catch (err) {
    if (statusEl) statusEl.textContent = `加载失败：${err.message}`;
    throw err;
  }
}

async function triggerSync(endpoint, statusEl) {
  if (statusEl) statusEl.textContent = "同步中…";
  try {
    const json = await fetchJson(endpoint, { method: "POST" });
    if (statusEl) {
      statusEl.textContent = json.ok
        ? "同步完成，正在刷新…"
        : `同步失败：${json.error || json.stderr || "未知错误"}`;
    }
    return json;
  } catch (err) {
    if (statusEl) statusEl.textContent = `同步失败：${err.message}`;
    throw err;
  }
}

window.CZ = { fetchJson, fmt, pct, renderTable, loadTable, triggerSync };
