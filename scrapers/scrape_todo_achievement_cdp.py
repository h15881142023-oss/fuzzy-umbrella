"""美团业务要求 / TODO 达成 CDP 抓取"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.meituan_scraper import run_scrape, save_todos


def main() -> int:
    return run_scrape(
        "scrape_todo_achievement_cdp",
        page_key="todo",
        keyword_key="todo",
        saver=save_todos,
    )


if __name__ == "__main__":
    raise SystemExit(main())
