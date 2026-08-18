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
CITY_CANON = {
    "彭州市": "彭州市",
    "彭州": "彭州市",
    "仁寿县": "仁寿县",
    "仁寿": "仁寿县",
    "合江县": "合江县",
    "合江": "合江县",
    "南溪": "南溪",
    "南溪区": "南溪",
    "南溪县": "南溪",
    "叙永": "叙永",
    "叙永县": "叙永",
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
    s = cell_str(v)
    if not s:
        return None
    if s in CITY_CANON:
        return CITY_CANON[s]
    s2 = s.replace(" ", "")
    return CITY_CANON.get(s2)


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


def load_peer_sheet(xlsx: Path) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(xlsx, sheet_name=SHEET_NAME, header=None, dtype=object)
    raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")
    raw = raw.reset_index(drop=True)
    if raw.empty:
        raise RuntimeError("子表「同分群数值对比」是空的")

    city_hits: list[tuple[int, int]] = []
    for r in range(len(raw)):
        for c in range(raw.shape[1]):
            if canon_city(raw.iat[r, c]):
                city_hits.append((r, c))

    meta = {"headerRows": [], "cityCol": None, "cities": []}
    if not city_hits:
        df = raw.copy()
        df.columns = unique_headers([cell_str(x) for x in df.iloc[0].tolist()])
        df = df.iloc[1:].reset_index(drop=True)
        meta["headerRows"] = [0]
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
                "headers": payload["headers"][:12],
                "headerRows": meta.get("headerRows"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
