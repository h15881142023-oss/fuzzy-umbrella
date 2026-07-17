#!/usr/bin/env python3
"""川藏一区 LR 利润日报（独立于网站）

流程骨架：
1. 从业务 API（如 chuxin.city）拉数 — 需本地登录态/Token
2. 写入 Excel
3. 截图为 PNG（待接）
4. 经企业微信发送

用法：
  cp .env.example .env   # 填写 WECOM_WEBHOOK / CHUXIN_TOKEN
  python run_daily.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)
CITIES = ["仁寿县", "南溪", "叙永", "彭州市", "合江县"]


def load_env() -> dict:
    env_path = ROOT / ".env"
    data = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("WECOM_WEBHOOK", "CHUXIN_TOKEN"):
        if os.environ.get(k):
            data[k] = os.environ[k]
    return data


def fetch_lr_rows(token: str | None) -> list[dict]:
    _ = token
    return [{"city": c, "profit": None, "note": "待接 API"} for c in CITIES]


def write_excel(rows: list[dict]) -> Path:
    import pandas as pd

    today = datetime.now().strftime("%Y-%m-%d")
    path = OUT / f"LR日报_{today}.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def wecom_send(webhook: str, text: str) -> dict:
    import urllib.request

    payload = json.dumps({"msgtype": "text", "text": {"content": text}}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    env = load_env()
    rows = fetch_lr_rows(env.get("CHUXIN_TOKEN"))
    xlsx = write_excel(rows)
    summary = f"【川藏一区 LR】{datetime.now():%Y-%m-%d} 已生成 {xlsx.name}（共 {len(rows)} 城）"
    print(summary)
    webhook = env.get("WECOM_WEBHOOK")
    if webhook:
        print("wecom:", wecom_send(webhook, summary))
    else:
        print("未配置 WECOM_WEBHOOK，跳过推送。见 lr/.env.example")
    (OUT / "last_run.json").write_text(
        json.dumps({"xlsx": str(xlsx), "rows": rows, "at": datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
