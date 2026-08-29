"""Windows helper: start Flask web on 0.0.0.0:5001。

ChuanzangWeb5001 开机自启后，create_app 会挂上新商评周二/周五 22:00 时钟，
对齐经营宝：不需要再从对话里复制 PowerShell。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app

app = create_app()
app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
