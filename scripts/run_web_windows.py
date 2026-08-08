"""Windows helper: start Flask web on 0.0.0.0:5001，并内嵌新商评周二/五 17:00 同步时钟。"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _start_xinshang_clock() -> None:
    import importlib.util

    clock = ROOT / "scripts" / "xinshang_clock_windows.py"
    spec = importlib.util.spec_from_file_location("xinshang_clock_windows", clock)
    if spec is None or spec.loader is None:
        print("xinshang clock: failed to load", flush=True)
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    t = threading.Thread(target=mod.loop_forever, name="xinshang-clock", daemon=True)
    t.start()
    print("xinshang clock thread started (Tue/Fri 17:00)", flush=True)


_start_xinshang_clock()

from app import create_app

app = create_app()
app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
