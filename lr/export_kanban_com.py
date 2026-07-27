"""Windows：通过 WPS/Excel COM 重算「看板-单城」并用剪贴板导出 PNG。"""
from __future__ import annotations

import glob
import os
import struct
import subprocess
import sys
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

_HKCR_ROOTS = (
    (winreg.HKEY_CLASSES_ROOT, ""),
    (winreg.HKEY_CLASSES_ROOT, r"WOW6432Node"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes\WOW6432Node"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\WOW6432Node"),
)


def _prog_ids_from_registry() -> list[str]:
    found: list[str] = []
    prefixes = ("Ket.Application", "KET.Application", "et.Application", "Excel.Application")
    for hive, sub in (
        (winreg.HKEY_CLASSES_ROOT, ""),
        (winreg.HKEY_CLASSES_ROOT, r"WOW6432Node"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes\WOW6432Node"),
    ):
        try:
            key = winreg.OpenKey(hive, sub) if sub else winreg.OpenKey(hive, "")
        except OSError:
            continue
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


def _read_reg_default(hive: int, path: str) -> str | None:
    try:
        key = winreg.OpenKey(hive, path)
    except OSError:
        return None
    try:
        val, _ = winreg.QueryValueEx(key, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except OSError:
        return None
    finally:
        winreg.CloseKey(key)
    return None


def _resolve_clsid(prog_id: str) -> str | None:
    """ProgID → {CLSID}；同时查 WOW6432Node（32 位 WPS + 64 位 Python 常见）。"""
    for hive, root in _HKCR_ROOTS:
        path = f"{root}\\{prog_id}\\CLSID" if root else f"{prog_id}\\CLSID"
        clsid = _read_reg_default(hive, path)
        if clsid and clsid.startswith("{") and clsid.endswith("}"):
            return clsid
    return None


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


def _pe_bits(exe: Path) -> int | None:
    try:
        with exe.open("rb") as f:
            if f.read(2) != b"MZ":
                return None
            f.seek(0x3C)
            pe_off = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_off)
            if f.read(4) != b"PE\0\0":
                return None
            machine = struct.unpack("<H", f.read(2))[0]
        if machine == 0x14C:
            return 32
        if machine == 0x8664:
            return 64
    except OSError:
        return None
    return None


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


def _try_create(prog_or_clsid: str, label: str, errors: list[str]):
    import win32com.client  # type: ignore

    for factory_name, factory in (
        ("Dispatch", lambda p: win32com.client.Dispatch(p)),
        ("DispatchEx", lambda p: win32com.client.DispatchEx(p)),
        ("dynamic.Dispatch", lambda p: win32com.client.dynamic.Dispatch(p)),
    ):
        try:
            app = factory(prog_or_clsid)
            return app, f"{label}/{factory_name}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}/{factory_name}: {exc}")
    return None, ""


def _dispatch_app():
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    # 任务计划/部分终端未初始化 COM 会直接 Invalid class string
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    errors: list[str] = []
    et_exes = _find_et_exes()
    candidates = _candidate_prog_ids()
    py_bits = 64 if sys.maxsize > 2**32 else 32
    et_bits = [_pe_bits(p) for p in et_exes[:3]]
    errors.append(f"python_bits={py_bits} et_bits={et_bits}")

    # 1) ProgID + CLSID（含 Wow6432Node）直接创建
    for prog_id in candidates:
        app, how = _try_create(prog_id, prog_id, errors)
        if app is not None:
            return app, how
        clsid = _resolve_clsid(prog_id)
        if clsid:
            app, how = _try_create(clsid, f"{prog_id}->{clsid}", errors)
            if app is not None:
                return app, how
        else:
            errors.append(f"{prog_id}: CLSID not found in HKCR/WOW6432Node")

    # 2) regserver + 启动 et.exe 后再附着
    for et in et_exes[:2]:
        _try_regserver(et)
        try:
            subprocess.Popen(
                [str(et)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(5)
            for prog_id in candidates:
                clsid = _resolve_clsid(prog_id)
                for token, label in (
                    (prog_id, prog_id),
                    (clsid, f"{prog_id}->{clsid}" if clsid else None),
                ):
                    if not token or not label:
                        continue
                    try:
                        app = win32com.client.GetActiveObject(token)
                        return app, f"{label}/GetActiveObject after {et.name}"
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"GetActiveObject {label}@{et.name}: {exc}")
                    app, how = _try_create(token, f"{label}/after-start", errors)
                    if app is not None:
                        return app, how
        except Exception as exc:  # noqa: BLE001
            errors.append(f"start {et}: {exc}")

    et_msg = ", ".join(str(p) for p in et_exes[:3]) or "(et.exe not found)"
    # 保留头尾错误：前面常是 ProgID 失败根因，后面是附着失败
    head = errors[:8]
    tail = errors[-8:] if len(errors) > 8 else []
    mid = ["..."] if len(errors) > 16 else []
    shown = head + mid + [e for e in tail if e not in head]
    hint = (
        " 若 PowerShell 里 Ket/Excel 已 OK 而 Python 仍失败，多半是 32/64 位不一致或仅注册在 WOW6432Node；"
        "已尝试 CLSID；将自动回退 PowerShell 导出。"
        f" et.exe={et_msg}"
    )
    raise RuntimeError("Cannot create WPS/Excel COM. " + " | ".join(shown) + hint)


def _save_clipboard_png(path: Path) -> None:
    from PIL import ImageGrab

    last: Exception | None = None
    for attempt in range(1, 10):
        try:
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
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.25 + attempt * 0.05)
    raise RuntimeError(f"failed to read clipboard after retries: {last}")


def _copy_range_to_clipboard(ws, address: str) -> None:
    import win32clipboard  # type: ignore

    for attempt in range(1, 10):
        try:
            try:
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
            time.sleep(0.35 + attempt * 0.05)
            return
        except Exception:
            time.sleep(0.25 + attempt * 0.05)
    rng = ws.Range(address)
    rng.CopyPicture(1, 2)
    time.sleep(0.5)


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
        f"python_bits={64 if sys.maxsize > 2**32 else 32}",
        f"prog_candidates={_candidate_prog_ids()[:12]}",
        f"et_exes={[str(p) for p in _find_et_exes()[:5]]}",
        f"et_bits={[ _pe_bits(p) for p in _find_et_exes()[:5] ]}",
        f"clsid_sample={{ {', '.join(f'{p}={_resolve_clsid(p)}' for p in _candidate_prog_ids()[:4])} }}",
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
