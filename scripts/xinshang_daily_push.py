"""新商评计划任务英文入口（对齐经营宝 daily_push.py，避免中文文件名乱码）。

流程：确保 Chrome CDP → Power BI 月在线商家数 → Metabase 主看板 → 同分群 → 企微。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_wecom_spec = importlib.util.spec_from_file_location(
    "xinshang_wecom",
    Path(__file__).with_name("xinshang_wecom.py"),
)
xinshang_wecom = importlib.util.module_from_spec(_wecom_spec)
assert _wecom_spec.loader is not None
_wecom_spec.loader.exec_module(xinshang_wecom)
DEFAULT_PAGE = xinshang_wecom.DEFAULT_PAGE
format_failure = xinshang_wecom.format_failure
format_success = xinshang_wecom.format_success
load_wecom_config = xinshang_wecom.load_wecom_config
send_text = xinshang_wecom.send_text

CDP_URL = "http://127.0.0.1:9222/json/version"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def last_json(text: str) -> dict:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    return {}


def test_cdp() -> bool:
    try:
        with urllib.request.urlopen(CDP_URL, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_chrome() -> bool:
    if test_cdp():
        log("CDP 9222 已就绪")
        return True
    if os.name != "nt":
        log("[WARN] 非 Windows，跳过启动 Power BI Chrome")
        return False
    ps1 = ROOT / "scripts" / "start_chrome_powerbi_windows.ps1"
    if not ps1.is_file():
        log("[WARN] 缺少 start_chrome_powerbi_windows.ps1")
        return False
    log("启动 Power BI Chrome（独立 profile，一般只需登录一次）")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
        ],
        cwd=str(ROOT),
        check=False,
    )
    if test_cdp():
        log("CDP 9222 已就绪")
        return True
    log("[WARN] Chrome 已开但 CDP 未就绪；若弹出登录请用 qiaoxh@ppu.powerbi.bi")
    return False


def run_py(rel: str, timeout: int = 900) -> dict:
    script = ROOT / rel
    if not script.is_file():
        return {"ok": False, "error": f"脚本不存在: {rel}", "stdout": "", "stderr": ""}
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = proc.stdout or ""
    err = proc.stderr or ""
    if out:
        print(out, end="" if out.endswith("\n") else "\n", flush=True)
    if err:
        print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr, flush=True)
    parsed = last_json(out)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": out,
        "stderr": err,
        "parsed": parsed,
        "error": "" if proc.returncode == 0 else (err.strip() or out.strip() or f"exit {proc.returncode}"),
    }


def notify(content: str, skip_wecom: bool) -> None:
    if skip_wecom:
        log("skip wecom: " + content.replace("\n", " | "))
        return
    cfg = load_wecom_config()
    log("wecom source=" + cfg.get("source", ""))
    send_text(content, cfg["webhook_url"])
    log("wecom sent")


def run_pipeline(*, skip_wecom: bool) -> int:
    log("==== start ====")
    log("root=" + str(ROOT))
    log("python=" + sys.executable)

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "websocket-client"],
            cwd=str(ROOT),
            check=False,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        log("[WARN] pip websocket-client: " + str(exc))

    chrome_ok = ensure_chrome()
    powerbi = "未跑"
    if chrome_ok:
        log("==> Power BI 月在线商家数")
        pbi = run_py("scrapers/scrape_powerbi_wind_online.py", timeout=300)
        if pbi["ok"]:
            powerbi = "成功"
        else:
            powerbi = "失败，沿用上次"
            log("[WARN] Power BI 抓取失败，主看板将沿用上次 JSON/默认值")
    else:
        powerbi = "CDP 未就绪，沿用上次"
        log("[WARN] 跳过 Power BI 抓取")

    log("==> Metabase 主看板")
    xin = run_py("scripts/sync_xinshang_from_chuxin.py")
    if not xin["ok"]:
        err = xin.get("error") or "sync_xinshang 失败"
        log("[BAD] " + err)
        try:
            notify(format_failure(err, "xinshang"), skip_wecom)
        except Exception as exc:  # noqa: BLE001
            log("[WARN] 企微失败通知也失败: " + str(exc))
        return 1

    log("==> 同分群对比")
    peer = run_py("scripts/sync_peer_compare_from_chuxin.py")
    if not peer["ok"]:
        err = peer.get("error") or "sync_peer_compare 失败"
        log("[BAD] " + err)
        try:
            notify(format_failure(err, "peer"), skip_wecom)
        except Exception as exc:  # noqa: BLE001
            log("[WARN] 企微失败通知也失败: " + str(exc))
        return 1

    xin_j = xin.get("parsed") or {}
    peer_j = peer.get("parsed") or {}
    summary = {
        "periodDate": peer_j.get("periodDate") or xin_j.get("date") or xin_j.get("periodDate"),
        "prevDate": peer_j.get("prevDate") or xin_j.get("prev"),
        "universeCities": peer_j.get("universeCities") or peer_j.get("cities"),
        "powerbi": powerbi,
        "page": DEFAULT_PAGE,
        "note": peer_j.get("cityUniverseNote") or "",
    }
    log("[OK] 新商评更新完成 " + json.dumps(summary, ensure_ascii=False))
    try:
        notify(format_success(summary), skip_wecom)
    except Exception as exc:  # noqa: BLE001
        log("[WARN] 企微成功通知失败（数据已写入）: " + str(exc))
    log("==== end ====")
    return 0


def self_test() -> int:
    cfg = load_wecom_config()
    ok_msg = format_success(
        {
            "periodDate": "2026-08-27",
            "prevDate": "2026-08-24",
            "universeCities": 117,
            "powerbi": "成功",
            "page": DEFAULT_PAGE,
        }
    )
    fail_msg = format_failure("demo error", "peer")
    sample = last_json('noise\n{"ok": true, "universeCities": 117}\n')
    checks = [
        bool(cfg.get("webhook_url")),
        "新商评看板已更新" in ok_msg,
        "新商评看板更新失败" in fail_msg,
        sample.get("universeCities") == 117,
        (ROOT / "scripts" / "run_xinshang_daily_push.bat").is_file(),
        (ROOT / "scripts" / "install_xinshang_task.ps1").is_file(),
    ]
    print(json.dumps({"ok": all(checks), "checks": checks, "wecomSource": cfg.get("source")}, ensure_ascii=False))
    return 0 if all(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="新商评周二/周五 22:00 入口")
    parser.add_argument("--once", action="store_true", help="兼容旧调用，行为与默认相同")
    parser.add_argument("--skip-wecom", action="store_true", help="只跑同步，不推企微")
    parser.add_argument("--self-test", action="store_true", help="不抓数，只校验入口与文案")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        return run_pipeline(skip_wecom=args.skip_wecom)
    except Exception as exc:  # noqa: BLE001
        log("[BAD] " + str(exc))
        try:
            if not args.skip_wecom:
                send_text(format_failure(str(exc), "pipeline"))
        except Exception as notify_exc:  # noqa: BLE001
            log("[WARN] 企微失败通知也失败: " + str(notify_exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
