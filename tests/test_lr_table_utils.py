import unittest
from datetime import date

from lr.table_utils import parse_scrape_payload


class ParseScrapePayloadTest(unittest.TestCase):
    def test_ignores_unnamed_row_number_column(self) -> None:
        payload = {
            "headers": ["区域", "城市", "日期"],
            "rows": [["1", "川藏一区", "仁寿县", "2026-07-19"]],
        }

        rows = parse_scrape_payload(payload)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["区域"], "川藏一区")
        self.assertEqual(rows[0]["组织结构"], "仁寿县")
        self.assertEqual(rows[0]["日"], date(2026, 7, 19))


if __name__ == "__main__":
    unittest.main()
