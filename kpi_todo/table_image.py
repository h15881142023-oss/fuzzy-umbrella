"""将 KPI 待办表格渲染为 PNG（美团黄表头 + 完成进度未达标标红）。"""
from __future__ import annotations

from pathlib import Path

from kpi_todo.table_utils import EXPECTED_HEADERS, parse_progress

# 美团黄 #FFC300
HEADER_BG = (255, 195, 0)
HEADER_FG = (34, 34, 34)  # 近黑，保证对比度
ROW_BG_A = (255, 255, 255)
ROW_BG_B = (255, 248, 224)  # 浅黄底交替，贴近美团浅色
GRID_COLOR = (220, 200, 120)
RED_BG = (255, 0, 0)
RED_FG = (255, 255, 255)
TEXT_FG = (20, 20, 20)

FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

# 12 列宽权重
COL_WEIGHTS = [0.9, 0.9, 0.8, 0.8, 0.9, 2.2, 0.8, 0.9, 0.8, 0.8, 0.8, 0.9]
CELL_PAD_X = 6
CELL_PAD_Y = 5
HEADER_HEIGHT = 34
MIN_ROW_HEIGHT = 28
FONT_SIZE = 13
HEADER_FONT_SIZE = 13


def _load_font(size: int):
    from PIL import ImageFont

    for path in FONT_PATHS:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines or [""]


def _progress_index() -> int:
    return EXPECTED_HEADERS.index("完成进度")


def render_table_png(
    headers: list[str],
    rows: list[list[str]],
    *,
    raw_rows: list[dict] | None = None,
    out_png: Path,
) -> Path:
    from PIL import Image, ImageDraw

    font = _load_font(FONT_SIZE)
    header_font = _load_font(HEADER_FONT_SIZE)
    progress_idx = _progress_index()

    usable_width = 1600
    n = len(headers)
    weights = COL_WEIGHTS[:n] if n <= len(COL_WEIGHTS) else COL_WEIGHTS + [1.0] * (n - len(COL_WEIGHTS))
    total_weight = sum(weights)
    col_widths = [max(56, int(usable_width * w / total_weight)) for w in weights]
    usable_width = sum(col_widths)

    wrapped_rows: list[list[list[str]]] = []
    row_heights: list[int] = []
    name_idx = headers.index("指标名称") if "指标名称" in headers else -1
    for row in rows:
        wrapped_cells: list[list[str]] = []
        max_lines = 1
        for c, cell in enumerate(row):
            lines = _wrap_text(cell, font, col_widths[c] - CELL_PAD_X * 2)
            # 指标名称允许多行，其他列最多 3 行避免图过高
            if c != name_idx:
                lines = lines[:3]
            wrapped_cells.append(lines)
            max_lines = max(max_lines, len(lines))
        h = max(MIN_ROW_HEIGHT, CELL_PAD_Y * 2 + max_lines * (FONT_SIZE + 3))
        row_heights.append(h)
        wrapped_rows.append(wrapped_cells)

    height = HEADER_HEIGHT + sum(row_heights) + 2
    img = Image.new("RGB", (usable_width + 2, height), "white")
    draw = ImageDraw.Draw(img)

    x0 = 1
    y = 1
    for c, title in enumerate(headers):
        w = col_widths[c]
        draw.rectangle([x0, y, x0 + w, y + HEADER_HEIGHT], fill=HEADER_BG, outline=GRID_COLOR)
        tw = header_font.getbbox(title)[2]
        tx = x0 + max(CELL_PAD_X, (w - tw) // 2)
        ty = y + (HEADER_HEIGHT - HEADER_FONT_SIZE) // 2
        draw.text((tx, ty), title, fill=HEADER_FG, font=header_font)
        x0 += w

    y += HEADER_HEIGHT
    for r, wrapped in enumerate(wrapped_rows):
        x0 = 1
        row_bg = ROW_BG_A if r % 2 == 0 else ROW_BG_B
        progress_val = None
        if raw_rows and r < len(raw_rows):
            progress_val = parse_progress(raw_rows[r].get("完成进度"))

        for c, lines in enumerate(wrapped):
            w = col_widths[c]
            cell_bg = row_bg
            cell_fg = TEXT_FG
            if c == progress_idx and progress_val is not None and progress_val < 1:
                cell_bg = RED_BG
                cell_fg = RED_FG

            draw.rectangle([x0, y, x0 + w, y + row_heights[r]], fill=cell_bg, outline=GRID_COLOR)
            line_y = y + CELL_PAD_Y
            for line in lines:
                draw.text((x0 + CELL_PAD_X, line_y), line, fill=cell_fg, font=font)
                line_y += FONT_SIZE + 3
            x0 += w
        y += row_heights[r]

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, format="PNG")
    return out_png
