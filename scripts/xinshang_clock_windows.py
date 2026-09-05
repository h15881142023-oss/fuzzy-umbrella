"""挂在 ChuanzangWeb5001 里的时钟：每周二、周五 22:00 自动跑新商评（对齐经营宝：装好 Web 后零操作）。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "xinshang_push.log"
TARGET_WEEKDAYS = {1, 4}  # Tuesday, Friday
TARGET_HOUR = 22
WINDOW_MINUTES = 10
THREAD_NAME = "xinshang-clock"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="", flush=True)


def _self_update() -> None:
    path = Path(__file__).with_name("xinshang_self_update.py")
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("xinshang_self_update", path)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.ensure_tools()
    if result.get("missing"):
        _log("self-update missing: " + ",".join(result["missing"]))


def run_once() -> int:
    _self_update()
    push = ROOT / "scripts" / "xinshang_daily_push.py"
    _log("==> xinshang sync start")
    if not push.is_file():
        _log("[BAD] missing xinshang_daily_push.py")
        return 1
    proc = subprocess.run(
        [sys.executable, str(push)],
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


def in_window(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return now.weekday() in TARGET_WEEKDAYS and now.hour == TARGET_HOUR and now.minute < WINDOW_MINUTES


def loop_forever() -> None:
    last_key: tuple | None = None
    _log("xinshang clock started (Tue/Fri 22:00 local, via ChuanzangWeb5001)")
    while True:
        now = datetime.now()
        if in_window(now):
            key = (now.date().isoformat(), now.weekday())
            if key != last_key:
                try:
                    run_once()
                except Exception as exc:  # noqa: BLE001
                    _log(f"sync error: {exc}")
                last_key = key
        time.sleep(30)


def start_background() -> bool:
    for t in threading.enumerate():
        if t.name == THREAD_NAME and t.is_alive():
            return False
    t = threading.Thread(target=loop_forever, name=THREAD_NAME, daemon=True)
    t.start()
    _log("xinshang clock thread started")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        raise SystemExit(run_once())
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        tue = datetime(2026, 9, 1, 22, 3)  # Tuesday
        sat = datetime(2026, 8, 29, 22, 3)
        ok = in_window(tue) and not in_window(sat)
        print({"ok": ok, "tue": in_window(tue), "sat": in_window(sat)})
        raise SystemExit(0 if ok else 1)
    loop_forever()
