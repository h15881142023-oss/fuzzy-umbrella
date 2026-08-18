"""从 Excel 子表「同分群数值对比」同步到新商看板（独立于主看板同步）。

用途：
1) 仅更新 DATA.peerCompare，不改动原有主看板数据同步逻辑。
2) 便于和 scripts/sync_xinshang_from_chuxin.py 分开执行。

表头经常不在第 1 行（标题 / 合并单元格 / 双行表头），这里会自动定位。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHEET_NAME = "同分群数值对比"
HTMLS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]
CITY_KEYS = [
    ("彭州市", ("彭州市", "彭州")),
    ("仁寿县", ("仁寿县", "仁寿")),
    ("合江县", ("合江县", "合江")),
    ("南溪", ("南溪区", "南溪县", "南溪")),
    ("叙永", ("叙永县", "叙永")),
]


TARGET_CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
TARGET_REGION = "川藏一区"
FIELD_ALIAS = {
    "最大值": "同分群最大值",
    "中位值": "同分群中位值",
    "最小值": "同分群最小值",
}


def pick_excel_path(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = ROOT / explicit
        if not p.exists():
            raise FileNotFoundError(f"Excel not found: {p}")
        return p
    cands = sorted(ROOT.glob("**/新商考核体系*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError("未找到『新商考核体系*.xlsx』，请通过 --xlsx 指定文件路径")
    return cands[0]


def cell_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    if isinstance(v, pd.Timestamp):
        if v.hour == 0 and v.minute == 0 and v.second == 0:
            return v.strftime("%Y-%m-%d")
        return v.isoformat()
    if isinstance(v, datetime):
        if v.hour == 0 and v.minute == 0 and v.second == 0:
            return v.strftime("%Y-%m-%d")
        return v.isoformat()
    if isinstance(v, date) and not isinstance(v, datetime):
        return v.isoformat()
    s = str(v).strip()
    if s.lower() in {"nan", "none", "nat"}:
        return ""
    return s


def canon_city(v) -> str | None:
    s = cell_str(v).replace(" ", "").replace("\n", "").replace("\r", "")
    if not s:
        return None
    hits = []
    for canon, keys in CITY_KEYS:
        for k in keys:
            if k in s:
                hits.append((len(k), canon))
                break
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def is_numbery(v) -> bool:
    s = cell_str(v).replace(",", "").replace("%", "")
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def preview_raw(raw: pd.DataFrame, n_rows: int = 10, n_cols: int = 12) -> list[list[str]]:
    out = []
    rr = min(n_rows, len(raw))
    cc = min(n_cols, raw.shape[1])
    for r in range(rr):
        out.append([cell_str(raw.iat[r, c])[:40] for c in range(cc)])
    return out


def ffill(vals: list[str]) -> list[str]:
    out = []
    last = ""
    for v in vals:
        if v:
            last = v
            out.append(v)
        else:
            out.append(last)
    return out


def unique_headers(names: list[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out = []
    for i, n in enumerate(names):
        name = n or f"列{i + 1}"
        seen[name] += 1
        if seen[name] == 1:
            out.append(name)
        else:
            out.append(f"{name}_{seen[name]}")
    return out


def pick_peer_sheet_name(xlsx: Path) -> str:
    xl = pd.ExcelFile(xlsx)
    cands = [n for n in xl.sheet_names if str(n).strip() == SHEET_NAME]
    if not cands:
        raise RuntimeError("Excel 中没有名为「同分群数值对比」的子表")
    best, best_n = cands[0], -1
    for n in cands:
        df = pd.read_excel(xlsx, sheet_name=n, header=None, dtype=object)
        if len(df) > best_n:
            best, best_n = n, len(df)
    return best


def normalize_cell(v):
    if isinstance(v, (pd.Timestamp, datetime, date)) or (hasattr(pd, "isna") and pd.isna(v)):
        s = cell_str(v)
        return s or None
    if isinstance(v, float):
        if pd.isna(v):
            return None
        return round(float(v), 6)
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    s = cell_str(v)
    return s if s != "" else None


def parse_official_peer(xlsx: Path) -> dict | None:
    """解析考核体系里真正的「同分群数值对比」宽表（三层表头：模块 / 指标 / 字段）。"""
    sheet = pick_peer_sheet_name(xlsx)
    raw = pd.read_excel(xlsx, sheet_name=sheet, header=None, dtype=object)
    raw = raw.dropna(axis=0, how="all")
    if raw.empty:
        return None
    n_cols = raw.shape[1]
    n_rows = len(raw)

    field_row = None
    for r in range(min(12, n_rows)):
        vals = [cell_str(raw.iat[r, c]) for c in range(min(n_cols, 8))]
        if "城市" in vals and "区域" in vals:
            field_row = r
            break
    if field_row is None or field_row < 1:
        return None

    metric_row = field_row - 1
    module_row = field_row - 2 if field_row >= 2 else field_row - 1
    modules = []
    metrics = []
    fields = []
    last_m = last_t = ""
    for c in range(n_cols):
        m = cell_str(raw.iat[module_row, c]) if module_row >= 0 else ""
        t = cell_str(raw.iat[metric_row, c])
        f = cell_str(raw.iat[field_row, c])
        if m:
            last_m = m
        if t:
            last_t = t
        modules.append(last_m)
        metrics.append(last_t)
        fields.append(FIELD_ALIAS.get(f, f))

    city_c = next((c for c in range(n_cols) if fields[c] == "城市"), 2)
    region_c = next((c for c in range(n_cols) if fields[c] == "区域"), 1)
    level_c = next((c for c in range(n_cols) if fields[c] == "城市等级"), 3)

    specs = []
    metric_ids = []
    for c in range(n_cols):
        field = fields[c]
        if field in {"辅助列", "区域", "城市", "城市等级", ""}:
            continue
        module = modules[c] or "其他"
        metric = metrics[c] or field
        mid = f"{module}-{metric}"
        if mid not in metric_ids:
            metric_ids.append(mid)
        specs.append({"idx": c, "module": module, "metric": metric, "field": field, "id": mid})

    metrics_meta = []
    for mid in metric_ids:
        hit = [s for s in specs if s["id"] == mid]
        metrics_meta.append(
            {
                "id": mid,
                "module": hit[0]["module"],
                "name": hit[0]["metric"],
                "fields": [s["field"] for s in hit],
            }
        )

    period = None
    for r in range(min(field_row, 6)):
        for c in range(min(6, n_cols)):
            if "本期日期" in cell_str(raw.iat[r, c]):
                period = cell_str(raw.iat[r, c + 1])[:10] if c + 1 < n_cols else None

    rows = []
    for r in range(field_row + 1, n_rows):
        raw_city = cell_str(raw.iat[r, city_c])
        city = canon_city(raw.iat[r, city_c]) or raw_city
        region = cell_str(raw.iat[r, region_c])
        if not city:
            continue
        values = {}
        for s in specs:
            values.setdefault(s["id"], {})[s["field"]] = normalize_cell(raw.iat[r, s["idx"]])
        rows.append(
            {
                "城市": city,
                "区域": region,
                "城市等级": cell_str(raw.iat[r, level_c]),
                "mine": city in TARGET_CITIES,
                "values": values,
            }
        )
    rows.sort(key=lambda x: (0 if x["mine"] else 1, x.get("区域") or "", x["城市"]))
    if not rows:
        return None

    mine_cities = [c for c in TARGET_CITIES if any(r["城市"] == c for r in rows)]
    all_cities = []
    seen_cities = set()
    for r in rows:
        if r["城市"] not in seen_cities:
            seen_cities.add(r["城市"])
            all_cities.append(r["城市"])

    # 扁平表：城市 + 各指标本期值，给旧渲染兜底
    flat_headers = ["城市", "区域", "城市等级"]
    for m in metrics_meta:
        for fld in ("本期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间"):
            if fld in m["fields"]:
                flat_headers.append(f"{m['name']}-{fld}")
    flat_rows = []
    for rec in rows:
        row = {"城市": rec["城市"], "区域": rec["区域"], "城市等级": rec["城市等级"]}
        for m in metrics_meta:
            block = rec["values"].get(m["id"]) or {}
            for fld in ("本期值", "同分群最大值", "同分群中位值", "同分群最小值", "分群", "预警区间"):
                if fld in m["fields"]:
                    row[f"{m['name']}-{fld}"] = block.get(fld)
        flat_rows.append(row)

    return {
        "sheet": sheet,
        "layout": "official",
        "periodDate": period,
        "cityField": "城市",
        "metrics": metrics_meta,
        "mineCities": mine_cities,
        "cities": mine_cities,
        "allCities": all_cities,
        "records": rows,
        "headers": flat_headers,
        "rows": flat_rows,
        "meta": {
            "layout": "official",
            "cities": mine_cities,
            "allCityCount": len(all_cities),
            "sheet": sheet,
            "periodDate": period,
            "headerRows": [module_row, metric_row, field_row],
        },
    }


def load_peer_sheet(xlsx: Path) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(xlsx, sheet_name=SHEET_NAME, header=None, dtype=object)
    raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")
    raw = raw.reset_index(drop=True)
    if raw.empty:
        raise RuntimeError("子表「同分群数值对比」是空的")

    meta = {
        "headerRows": [],
        "cityCol": None,
        "cities": [],
        "layout": "row",
        "preview": preview_raw(raw),
        "shape": [int(raw.shape[0]), int(raw.shape[1])],
    }
    n_cols = raw.shape[1]
    n_rows = len(raw)

    def row_vals(r: int) -> list[str]:
        return [cell_str(raw.iat[r, c]) for c in range(n_cols)]

    def row_cities(r: int) -> list[tuple[int, str]]:
        out = []
        for c in range(n_cols):
            city = canon_city(raw.iat[r, c])
            if city:
                out.append((c, city))
        return out

    def col_cities(c: int) -> list[tuple[int, str]]:
        out = []
        for r in range(n_rows):
            city = canon_city(raw.iat[r, c])
            if city:
                out.append((r, city))
        return out

    def nonempty_count(r: int) -> int:
        return sum(1 for x in row_vals(r) if x)

    start = 0
    while start < n_rows and nonempty_count(start) <= 2 and not row_cities(start) and not any(is_numbery(raw.iat[start, c]) for c in range(n_cols)):
        start += 1

    best_row = max(range(start, n_rows), key=lambda r: len(row_cities(r)), default=start)
    best_col = max(range(n_cols), key=lambda c: len(col_cities(c)), default=0)
    row_hits = row_cities(best_row)
    col_hits = col_cities(best_col)

    # 城市在列上（一行里出现多个城市）→ 转成「城市为行、指标为列」
    if len(row_hits) >= 2 and len(row_hits) >= len(col_hits):
        meta["layout"] = "columns"
        meta["headerRows"] = [best_row]
        city_by_col = {c: name for c, name in row_hits}
        metric_cols = [c for c in range(n_cols) if c not in city_by_col]
        metric_col = metric_cols[0] if metric_cols else 0
        wide: dict[str, dict] = {name: {"城市": name} for name in dict.fromkeys(city_by_col.values())}
        for r in range(best_row + 1, n_rows):
            metric = cell_str(raw.iat[r, metric_col])
            if not metric or canon_city(metric):
                extra = [c for c in metric_cols if c != metric_col and cell_str(raw.iat[r, c]) and not is_numbery(raw.iat[r, c])]
                if extra and not metric:
                    metric = cell_str(raw.iat[r, extra[0]])
            if not metric or canon_city(metric):
                continue
            for c, city in city_by_col.items():
                val = raw.iat[r, c]
                if cell_str(val) == "" and c != metric_col:
                    continue
                wide[city][metric] = val
        df = pd.DataFrame(list(wide.values()))
        order = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
        meta["cities"] = [c for c in order if c in set(df["城市"].tolist())]
        meta["cityCol"] = "城市"
        keep = ["城市"] + [c for c in df.columns if c != "城市"]
        return df[keep], meta

    city_hits: list[tuple[int, int]] = []
    for r in range(start, n_rows):
        for c in range(n_cols):
            if canon_city(raw.iat[r, c]):
                city_hits.append((r, c))

    if not city_hits:
        header_i = start
        df = raw.iloc[header_i:].copy()
        df.columns = unique_headers([cell_str(x) for x in df.iloc[0].tolist()])
        df = df.iloc[1:].reset_index(drop=True)
        meta["headerRows"] = [header_i]
        meta["layout"] = "unknown"
        return df, meta

    first_data = min(r for r, _ in city_hits)
    pre = [i for i in range(start, first_data) if nonempty_count(i)]
    header_rows = pre[-2:] if len(pre) >= 2 else (pre[-1:] if pre else [max(start, first_data - 1)])
    meta["headerRows"] = header_rows
    meta["layout"] = "row"

    if len(header_rows) == 1:
        names = ffill([cell_str(raw.iat[header_rows[0], c]) for c in range(n_cols)])
    else:
        top = ffill([cell_str(raw.iat[header_rows[0], c]) for c in range(n_cols)])
        bot = [cell_str(raw.iat[header_rows[1], c]) for c in range(n_cols)]
        names = []
        for t, b in zip(top, bot):
            if t and b and t != b:
                names.append(f"{t}-{b}")
            else:
                names.append(b or t)
        names = ffill(names)
    headers = unique_headers(names)

    df = raw.iloc[first_data:].copy()
    df.columns = headers
    df = df.reset_index(drop=True)

    city_col_idx = Counter(c for _, c in city_hits if _ >= first_data).most_common(1)[0][0]
    city_col_name = headers[city_col_idx]
    named = next((h for h in headers if "城市" in str(h)), None)
    if named:
        city_col_name = named
    meta["cityCol"] = city_col_name

    cities = []
    canon_vals = []
    for _, rec in df.iterrows():
        city = canon_city(rec.get(city_col_name))
        if not city:
            for h in headers:
                city = canon_city(rec.get(h))
                if city:
                    break
        canon_vals.append(city)
        if city:
            cities.append(city)
    if city_col_name == "城市":
        df["城市"] = canon_vals
    else:
        df.insert(0, "城市", canon_vals)

    order = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
    meta["cities"] = sorted(set(cities), key=lambda x: order.index(x) if x in order else 99)
    keep = []
    for c in df.columns:
        if c == "城市" or any(cell_str(v) for v in df[c].tolist()):
            keep.append(c)
    df = df[keep]
    return df, meta

    first_data = min(r for r, _ in city_hits)
    pre = [i for i in range(first_data) if any(cell_str(x) for x in raw.iloc[i].tolist())]
    header_rows = pre[-2:] if len(pre) >= 2 else (pre[-1:] if pre else [max(0, first_data - 1)])
    meta["headerRows"] = header_rows

    n_cols = raw.shape[1]
    if len(header_rows) == 1:
        names = [cell_str(raw.iat[header_rows[0], c]) for c in range(n_cols)]
        names = ffill(names)
    else:
        top = ffill([cell_str(raw.iat[header_rows[0], c]) for c in range(n_cols)])
        bot = [cell_str(raw.iat[header_rows[1], c]) for c in range(n_cols)]
        names = []
        for t, b in zip(top, bot):
            if t and b and t != b:
                names.append(f"{t}-{b}")
            else:
                names.append(b or t)
        names = ffill(names)
    headers = unique_headers(names)

    df = raw.iloc[first_data:].copy()
    df.columns = headers
    df = df.reset_index(drop=True)

    city_col_idx = Counter(c for _, c in city_hits if _ >= first_data).most_common(1)[0][0]
    city_col_name = headers[city_col_idx]
    named = next((h for h in headers if "城市" in str(h)), None)
    if named:
        city_col_name = named
    meta["cityCol"] = city_col_name

    cities = []
    canon_vals = []
    for _, rec in df.iterrows():
        city = canon_city(rec.get(city_col_name))
        if not city:
            for h in headers:
                city = canon_city(rec.get(h))
                if city:
                    break
        canon_vals.append(city)
        if city:
            cities.append(city)
    if city_col_name == "城市":
        df["城市"] = canon_vals
    else:
        df.insert(0, "城市", canon_vals)

    order = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]
    meta["cities"] = sorted(set(cities), key=lambda x: order.index(x) if x in order else 99)
    # drop columns that are empty
    keep = []
    for c in df.columns:
        series = df[c]
        if c == "城市":
            keep.append(c)
            continue
        nonempty = any(cell_str(v) for v in series.tolist())
        if nonempty:
            keep.append(c)
    df = df[keep]
    return df, meta


def to_rows(df: pd.DataFrame) -> list[dict]:
    def normalize_cell(v):
        if isinstance(v, (pd.Timestamp, datetime, date)) or (hasattr(pd, "isna") and pd.isna(v)):
            s = cell_str(v)
            return s or None
        if isinstance(v, float):
            if pd.isna(v):
                return None
            return round(v, 6)
        s = cell_str(v)
        return s if s != "" else None

    out: list[dict] = []
    for rec in df.to_dict(orient="records"):
        row = {}
        for k, v in rec.items():
            row[str(k)] = normalize_cell(v)
        out.append(row)
    return out


def extract_data_json(html: str) -> tuple[int, int, dict]:
    marker = "const DATA = "
    start = html.index(marker) + len(marker)
    while html[start].isspace():
        start += 1
    depth = 0
    in_str = False
    esc = False
    end = None
    for j, ch in enumerate(html[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        raise RuntimeError("无法定位 DATA JSON 结束位置")
    payload = json.loads(html[start:end])
    return start, end, payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", help="Excel 文件路径（可选）")
    args = ap.parse_args()

    xlsx = pick_excel_path(args.xlsx)
    official = parse_official_peer(xlsx)
    if official:
        payload = official
        payload["sourceFile"] = Path(xlsx).name
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        meta = payload.get("meta") or {}
    else:
        df, meta = load_peer_sheet(xlsx)
        payload = {
            "sheet": SHEET_NAME,
            "sourceFile": str(xlsx),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "cityField": "城市",
            "headers": list(df.columns),
            "rows": to_rows(df),
            "meta": meta,
        }

    html = HTMLS[0].read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)
    data["peerCompare"] = payload
    new_html = html[:start] + json.dumps(data, ensure_ascii=False, indent=2) + html[end:]

    for p in HTMLS:
        p.write_text(new_html, encoding="utf-8")
        print("wrote", p)
    print(
        json.dumps(
            {
                "ok": True,
                "xlsx": str(xlsx),
                "rows": len(payload["rows"]),
                "cities": meta.get("cities"),
                "layout": meta.get("layout"),
                "headers": payload["headers"][:12],
                "periodDate": meta.get("periodDate") or payload.get("periodDate"),
                "metrics": len(payload.get("metrics") or []),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
