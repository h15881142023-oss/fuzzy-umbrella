import unittest

from openpyxl import Workbook

from lr.fill_template import HEADER_ROW, _header_col_map


class HeaderColumnMapTest(unittest.TestCase):
    def test_uses_first_duplicate_header(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.cell(HEADER_ROW, 3, "日")
        sheet.cell(HEADER_ROW, 47, "日")

        mapping = _header_col_map(sheet)

        self.assertEqual(mapping["日"], 3)
        workbook.close()


if __name__ == "__main__":
    unittest.main()
