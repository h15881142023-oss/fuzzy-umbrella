"""从 Excel 子表「同分群数值对比」同步到新商看板（独立于主看板同步）。

用途：
1) 仅更新 DATA.peerCompare，不改动原有主看板数据同步逻辑。
2) 便于和 scripts/sync_xinshang_from_chuxin.py 分开执行。
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHEET_NAME = "同分群数值对比"
HTMLS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]


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


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    cols = [str(c).strip() if c is not None else "" for c in df.columns]
    df.columns = cols
    return df


def to_rows(df: pd.DataFrame) -> list[dict]:
    def normalize_cell(v):
        if pd.isna(v):
            return None
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, float):
            return round(v, 6)
        return v

    out: list[dict] = []
    for rec in df.to_dict(orient="records"):
        row = {}
        for k, v in rec.items():
            row[k] = normalize_cell(v)
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
    df = pd.read_excel(xlsx, sheet_name=SHEET_NAME)
    df = clean_df(df)
    payload = {
        "sheet": SHEET_NAME,
        "sourceFile": str(xlsx),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "headers": list(df.columns),
        "rows": to_rows(df),
    }

    html = HTMLS[0].read_text(encoding="utf-8")
    start, end, data = extract_data_json(html)
    data["peerCompare"] = payload
    new_html = html[:start] + json.dumps(data, ensure_ascii=False, indent=2) + html[end:]

    for p in HTMLS:
        p.write_text(new_html, encoding="utf-8")
        print("wrote", p)
    print(json.dumps({"ok": True, "xlsx": str(xlsx), "rows": len(payload["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
