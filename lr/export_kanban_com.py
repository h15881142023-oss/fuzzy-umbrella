"""Windows：通过 WPS/Excel COM 重算「看板-单城」并用剪贴板导出 PNG。"""
from __future__ import annotations

import os
import time
import winreg
from datetime import date
from pathlib import Path

from config import CITIES, REGION_NAME

KANBAN_SHEET = "看板-单城"
RANGE_ADDRESS = "B1:R37"

# 常见 ProgID；再叠加注册表扫描结果
BASE_PROG_IDS = (
    "Ket.Application",
    "et.Application",
    "Excel.Application",
    "Ket.Application.9",
    "Ket.Application.12",
    "et.Application.9",
    "et.Application.12",
)


def _prog_ids_from_registry() -> list[str]:
    found: list[str] = []
    roots = [
        (winreg.HKEY_CLASSES_ROOT, r""),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Classes"),
    ]
    prefixes = ("Ket.Application", "et.Application", "Excel.Application")
    for hive, sub in roots:
        try:
            base = winreg.OpenKey(hive, sub) if sub else winreg.ConnectRegistry(None, hive)
            if sub == "" and hive == winreg.HKEY_CLASSES_ROOT:
                key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
            else:
                key = base if sub == "" else winreg.OpenKey(hive, sub)
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
            try:
                winreg.CloseKey(key)
            except OSError:
                pass
    return found


def _candidate_prog_ids() -> list[str]:
    ordered: list[str] = []
    for pid in list(BASE_PROG_IDS) + _prog_ids_from_registry():
        if pid not in ordered:
            ordered.append(pid)
    # 环境变量可强制指定，例如 LR_WPS_PROGID=Ket.Application
    forced = os.environ.get("LR_WPS_PROGID", "").strip()
    if forced:
        ordered.insert(0, forced)
    return ordered


def _dispatch_app():
    import win32com.client  # type: ignore

    errors: list[str] = []
    for prog_id in _candidate_prog_ids():
        for factory in (
            lambda p: win32com.client.Dispatch(p),
            lambda p: win32com.client.DispatchEx(p),
            lambda p: win32com.client.gencache.EnsureDispatch(p),
        ):
            try:
                app = factory(prog_id)
                return app, prog_id
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{prog_id}: {exc}")
                continue
    hint = (
        " WPS COM 未注册。请在本机普通（非管理员）窗口手动打开一次 WPS 表格，"
        "或设置环境变量 LR_WPS_PROGID。计划任务务必用「只在用户登录时运行」且不要勾选最高权限。"
    )
    raise RuntimeError("Cannot create WPS/Excel COM. " + " | ".join(errors[-8:]) + hint)


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
