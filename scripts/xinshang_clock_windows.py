"""后台时钟：每周二、五 17:00 自动同步新商评看板。

可独立常驻，也可由 run_web_windows.py 以内嵌线程启动。
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update_xinshang_dashboard.py"
LOG = ROOT / "logs" / "xinshang_sync.log"
# Monday=0 ... Tuesday=1, Friday=4
TARGET_WEEKDAYS = {1, 4}
TARGET_HOUR = 17
# 17:00–17:09 窗口内只跑一次
WINDOW_MINUTES = 10


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="", flush=True)


def run_once() -> int:
    _log("==> xinshang sync start")
    proc = subprocess.run(
        [sys.executable, str(UPDATER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.stdout:
        _log(proc.stdout.strip())
    if proc.stderr:
        _log("stderr: " + proc.stderr.strip())
    _log(f"==> xinshang sync done exit={proc.returncode}")
    return int(proc.returncode)


def loop_forever() -> None:
    last_key: tuple | None = None
    _log("xinshang clock started (Tue/Fri 17:00 local)")
    while True:
        now = datetime.now()
        if (
            now.weekday() in TARGET_WEEKDAYS
            and now.hour == TARGET_HOUR
            and now.minute < WINDOW_MINUTES
        ):
            key = (now.date().isoformat(), now.weekday())
            if key != last_key:
                try:
                    run_once()
                except Exception as exc:  # noqa: BLE001
                    _log(f"sync error: {exc}")
                last_key = key
        time.sleep(30)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        raise SystemExit(run_once())
    loop_forever()
