"""美团通知中心 CDP 抓取"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.meituan_scraper import run_scrape, save_notices


def main() -> int:
    return run_scrape(
        "scrape_meituan_cdp",
        page_key="notice",
        keyword_key="notice",
        saver=save_notices,
    )


if __name__ == "__main__":
    raise SystemExit(main())
