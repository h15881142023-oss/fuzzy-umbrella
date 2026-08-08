"""修复部分 Excel 模板中 openpyxl 无法解析的 autoFilter。"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


def sanitize_for_openpyxl(src: Path, dst: Path) -> Path:
    """复制 xlsx 并移除 worksheet 内无效的 autoFilter 节点。"""
    print(f"[lr] sanitize copy {src.name} -> {dst.name} ...", flush=True)
    shutil.copy2(src, dst)
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("[lr] sanitize unzip ...", flush=True)
        with zipfile.ZipFile(dst, "r") as zin:
            zin.extractall(tmp_path)
        changed = 0
        for sheet_xml in tmp_path.rglob("sheet*.xml"):
            text = sheet_xml.read_text(encoding="utf-8")
            new_text = re.sub(r"<autoFilter[^>]*/>", "", text)
            new_text = re.sub(r"<autoFilter[^>]*>.*?</autoFilter>", "", new_text, flags=re.DOTALL)
            if new_text != text:
                sheet_xml.write_text(new_text, encoding="utf-8")
                changed += 1
        print(f"[lr] sanitize rezip (sheets_changed={changed}) ...", flush=True)
        with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for file in sorted(tmp_path.rglob("*")):
                if file.is_file():
                    zout.write(file, file.relative_to(tmp_path).as_posix())
    print("[lr] sanitize done", flush=True)
    return dst
