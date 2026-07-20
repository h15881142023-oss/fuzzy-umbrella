"""将「看板-单城」工作表渲染为 PNG（无 LibreOffice 时用 openpyxl 读值 + Pillow）。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from openpyxl import load_workbook

KANBAN_SHEET = "看板-单城"
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
)


def _load_font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_with_pillow(xlsx: Path, out_png: Path) -> Path:
    from PIL import Image, ImageDraw

    wb = load_workbook(xlsx, data_only=True)
    ws = wb[KANBAN_SHEET]
    lines: list[str] = []
    title = ws.cell(1, 2).value or "看板-单城"
    lines.append(str(title))
    lines.append("")

    for r in range(2, min(ws.max_row, 20) + 1):
        cells = []
        for c in range(2, min(ws.max_column, 12) + 1):
            v = ws.cell(r, c).value
            if v is None:
                continue
            if hasattr(v, "strftime"):
                v = v.strftime("%Y-%m-%d")
            elif isinstance(v, float):
                v = f"{v:.4g}" if abs(v) < 1 else f"{v:.2f}"
            cells.append(str(v))
        if cells:
            lines.append(" | ".join(cells))
    wb.close()

    font = _load_font(14)
    title_font = _load_font(18)
    line_h = 24
    width = 1200
    height = max(400, 40 + line_h * len(lines))
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 16
    for i, line in enumerate(lines):
        f = title_font if i == 0 else font
        if i == 0:
            draw.text((16, y), line, fill=(0, 80, 160), font=f)
        else:
            draw.text((16, y), line[:180], fill=(20, 20, 20), font=f)
        y += line_h

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, format="PNG")
    return out_png


def _render_with_libreoffice(xlsx: Path, out_dir: Path) -> Path | None:
    for cmd in ("soffice", "libreoffice"):
        try:
            subprocess.run(
                [cmd, "--headless", "--convert-to", "png", "--outdir", str(out_dir), str(xlsx)],
                check=True,
                capture_output=True,
                timeout=120,
            )
            pngs = sorted(out_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            return pngs[0] if pngs else None
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None


def export_kanban_png(xlsx: Path, out_png: Path) -> Path:
    png = _render_with_libreoffice(xlsx, out_png.parent)
    if png and png.exists():
        if png != out_png:
            png.replace(out_png)
        return out_png
    return _render_with_pillow(xlsx, out_png)
