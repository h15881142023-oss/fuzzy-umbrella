"""一键：从初心抓取川藏一区新商评 → 生成域名看板 HTML。

用法（项目根目录）:
  python scripts/update_xinshang_dashboard.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    scrape = ROOT / "scrapers" / "scrape_chuxin_xinshang.py"
    build = ROOT / "scripts" / "build_xinshang_dashboard.py"
    py = sys.executable
    print("==> scrape chuxin xinshang")
    subprocess.check_call([py, str(scrape)], cwd=str(ROOT))
    print("==> build dashboard html")
    subprocess.check_call([py, str(build)], cwd=str(ROOT))
    outs = [
        ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
        ROOT / "docs" / "xinshang" / "index.html",
    ]
    for p in outs:
        print("ready:", p)
    print("domain path: /evaluation/xinshang")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
