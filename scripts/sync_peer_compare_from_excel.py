"""【已停用】原 Excel「同分群数值对比」同步脚本。

请改用：
  python scripts/sync_peer_compare_from_chuxin.py
  或 Windows：scripts\\sync_peer_compare_windows.ps1

同分群数据现从初心「新商考核」各模块 Tab 拉取，并按分群自算最大/中位/最小。
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "[DEPRECATED] Excel 同分群同步已停用。\n"
        "请运行: python scripts/sync_peer_compare_from_chuxin.py",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
