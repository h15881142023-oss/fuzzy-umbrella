"""Windows：通过 WPS/Excel COM 重算「看板-单城」并用剪贴板导出 PNG。"""
from __future__ import annotations

import glob
import os
import subprocess
import time
import winreg
from datetime import date
from pathlib import Path

from config import CITIES, REGION_NAME

KANBAN_SHEET = "看板-单城"
RANGE_ADDRESS = "B1:R37"

# 注意：本机诊断常见为 KET.Application / Excel.Application 可用，et.Application 反而不注册
BASE_PROG_IDS = (
    "KET.Application",
    "Ket.Application",
    "KET.Application.9",
    "Ket.Application.9",
    "Excel.Application",
    "Excel.Application.12",
    "Excel.Application.11",
    "et.Application",
    "et.Application.9",
)


def _prog_ids_from_registry() -> list[str]:
    found: list[str] = []
    prefixes = ("Ket.Application", "et.Application", "Excel.Application")
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
    except OSError:
        return found
    try:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            if any(name == p or name.startswith(p + ".") for p in prefixes):
                if name not in found:
                    found.append(name)
    finally:
        winreg.CloseKey(key)
    return found


def _candidate_prog_ids() -> list[str]:
    ordered: list[str] = []
    for pid in list(BASE_PROG_IDS) + _prog_ids_from_registry():
        if pid not in ordered:
            ordered.append(pid)
    forced = os.environ.get("LR_WPS_PROGID", "").strip()
    if forced:
        ordered.insert(0, forced)
    return ordered


def _find_et_exes() -> list[Path]:
    patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Kingsoft\WPS Office\*\office6\et.exe"),
        os.path.expandvars(r"%ProgramFiles%\Kingsoft\WPS Office\*\office6\et.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Kingsoft\WPS Office\*\office6\et.exe"),
    ]
    env = os.environ.get("LR_WPS_ET_EXE", "").strip()
    out: list[Path] = []
    if env and Path(env).exists():
        out.append(Path(env))
    for pat in patterns:
        for hit in sorted(glob.glob(pat), reverse=True):
            p = Path(hit)
            if p.exists() and p not in out:
                out.append(p)
    return out


def _try_regserver(et_exe: Path) -> None:
    try:
        subprocess.run(
            [str(et_exe), "/regserver"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception:
        pass


def _dispatch_app():
    import win32com.client  # type: ignore

    errors: list[str] = []
    et_exes = _find_et_exes()

    # 1) 若找到 et.exe，先尝试 /regserver 再 Dispatch
    for et in et_exes[:2]:
        _try_regserver(et)

    for prog_id in _candidate_prog_ids():
        for factory_name, factory in (
            ("Dispatch", lambda p: win32com.client.Dispatch(p)),
            ("DispatchEx", lambda p: win32com.client.DispatchEx(p)),
        ):
            try:
                app = factory(prog_id)
                return app, f"{prog_id}/{factory_name}"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{prog_id}/{factory_name}: {exc}")

    # 2) 启动 et.exe 后再 GetActiveObject / Dispatch
    for et in et_exes[:2]:
        try:
            subprocess.Popen(
                [str(et)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(4)
            for prog_id in _candidate_prog_ids():
                try:
                    app = win32com.client.GetActiveObject(prog_id)
                    return app, f"{prog_id}/GetActiveObject after {et.name}"
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"GetActiveObject {prog_id}@{et}: {exc}")
                try:
                    app = win32com.client.Dispatch(prog_id)
                    return app, f"{prog_id}/Dispatch after start {et.name}"
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Dispatch-after-start {prog_id}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"start {et}: {exc}")

    et_msg = ", ".join(str(p) for p in et_exes[:3]) or "(et.exe not found)"
    hint = (
        " WPS COM 未注册。"
        "请用【普通权限】PowerShell 运行: "
        "powershell -ExecutionPolicy Bypass -File scripts\\diagnose_wps_com.ps1"
        f" ; et.exe candidates={et_msg}"
    )
    raise RuntimeError("Cannot create WPS/Excel COM. " + " | ".join(errors[-10:]) + hint)


def _save_clipboard_png(path: Path) -> None:
    from PIL import ImageGrab

    img = ImageGrab.grabclipboard()
    if img is None:
        raise RuntimeError("Clipboard empty after CopyPicture")
    if isinstance(img, list):
        raise RuntimeError(f"Clipboard returned files instead of image: {img}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    img.save(path, format="PNG")
    if not path.exists() or path.stat().st_size < 100:
        raise RuntimeError(f"PNG too small or missing: {path}")


def _copy_range_to_clipboard(ws, address: str) -> None:
    try:
        import win32clipboard  # type: ignore

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
    except Exception:
        pass
    rng = ws.Range(address)
    try:
        rng.CopyPicture(1, 2)
    except Exception:
        rng.CopyPicture(Appearance=1, Format=2)
    time.sleep(0.35)


def _calculate(app, wb) -> None:
    for fn in ("CalculateFullRebuild", "CalculateFull", "Calculate"):
        try:
            getattr(app, fn)()
            return
        except Exception:
            continue
    try:
        wb.Application.Calculate()
    except Exception:
        pass


def export_kanban_pngs_com(
    xlsx: Path,
    out_dir: Path,
    target: date,
    cities: list[str] | None = None,
    *,
    sheet_name: str = KANBAN_SHEET,
    range_address: str = RANGE_ADDRESS,
    region: str = REGION_NAME,
) -> list[Path]:
    """Open workbook in WPS/Excel, switch city, CopyPicture → PNG for each city."""
    cities = cities or list(CITIES)
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_abs = str(xlsx.resolve())
    log_path = out_dir / "wps_export.log"
    lines: list[str] = [
        f"xlsx={xlsx_abs}",
        f"month={target.month}",
        f"cities={cities}",
        f"prog_candidates={_candidate_prog_ids()[:12]}",
        f"et_exes={[str(p) for p in _find_et_exes()[:5]]}",
    ]

    app = None
    wb = None
    try:
        app, prog_id = _dispatch_app()
        lines.append(f"prog_id={prog_id}")
        try:
            app.Visible = True
        except Exception:
            pass
        try:
            app.DisplayAlerts = False
        except Exception:
            pass

        wb = app.Workbooks.Open(xlsx_abs, 0, False)
        try:
            ws = wb.Worksheets(sheet_name)
        except Exception as exc:
            names = []
            try:
                names = [wb.Worksheets(i).Name for i in range(1, wb.Worksheets.Count + 1)]
            except Exception:
                pass
            raise RuntimeError(f"Sheet not found: {sheet_name}; sheets={names}") from exc

        ws.Activate()
        ws.Range("C2").Value2 = int(target.month)
        ws.Range("E3").Value2 = region
        _calculate(app, wb)

        pngs: list[Path] = []
        for city in cities:
            ws.Range("C3").Value2 = city
            _calculate(app, wb)
            time.sleep(0.45)
            safe = "".join("_" if c in '\\/:*?"<>|' else c for c in city)
            png = out_dir / f"看板-单城_{safe}_{target.month}.png"
            _copy_range_to_clipboard(ws, range_address)
            _save_clipboard_png(png)
            pngs.append(png)
            lines.append(f"exported={png}")

        wb.Save()
        lines.append(f"ok count={len(pngs)}")
        return pngs
    except Exception as exc:
        lines.append(f"ERROR={type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass
        if wb is not None:
            try:
                wb.Close(True)
            except Exception:
                try:
                    wb.Close(False)
                except Exception:
                    pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
            try:
                del app
            except Exception:
                pass
