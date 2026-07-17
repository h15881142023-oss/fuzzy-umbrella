"""美团 unitDashboard CDP 抓取 → dashboard_metrics / dashboard_snapshots"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.meituan_scraper import run_scrape, save_dashboard


def main() -> int:
    return run_scrape(
        "scrape_dashboard_cdp",
        page_key="dashboard",
        keyword_key="dashboard",
        saver=save_dashboard,
    )


if __name__ == "__main__":
    raise SystemExit(main())
