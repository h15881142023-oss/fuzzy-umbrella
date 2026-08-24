#!/usr/bin/env python3
"""Verify kanban PNGs exist per export config JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_dir = Path(cfg["outDir"])
    month = int(cfg["month"])
    prefix = str(cfg.get("pngPrefix") or "kanban")
    cities = list(cfg.get("cities") or [])
    missing: list[str] = []

    for city in cities:
        safe = "".join("_" if c in '\\/:*?"<>|' else c for c in str(city))
        png = out_dir / f"{prefix}_{safe}_{month}.png"
        if not png.exists() or png.stat().st_size < 100:
            missing.append(str(png))

    if missing:
        print("missing pngs:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(f"ok count={len(cities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
