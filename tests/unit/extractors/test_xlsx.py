"""Tests for XlsxExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.xlsx import XlsxExtractor


def _make_cell(value):
    cell = MagicMock()
    cell.value = value
    return cell


def _make_worksheet(name: str, rows_data: list[list]) -> MagicMock:
    ws = MagicMock()
    ws.title = name
    rows = []
    for row_data in rows_data:
        rows.append(tuple(_make_cell(v) for v in row_data))
    ws.iter_rows.return_value = rows
    return ws


class TestXlsxExtractor:
    def setup_method(self):
        self.ext = XlsxExtractor()

    def test_can_handle(self):
        assert self.ext.can_handle("data.xlsx")
        assert self.ext.can_handle("DATA.XLSX")
        assert not self.ext.can_handle("data.xls")
        assert not self.ext.can_handle("data.csv")

    def test_extract_mocked(self):
        """Test extraction with mocked openpyxl."""
        ws = _make_worksheet("Sheet1", [["Name", "Age"], ["Alice", "30"]])

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=ws)
        mock_wb.close = MagicMock()

        mock_openpyxl = MagicMock()
        mock_openpyxl.load_workbook.return_value = mock_wb

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = self.ext.extract("test.xlsx")

        assert result.source_type == "xlsx"
        assert "Name" in result.text
        assert "Alice" in result.text
        assert result.metadata["Sheets"] == "Sheet1"
        assert result.metadata["Total rows"] == 2
        mock_wb.close.assert_called_once()

    def test_markdown_sheet_headers(self):
        """Test that sheets get ## Sheet: Name headers."""
        ws1 = _make_worksheet("MySheet", [["A", "B"], ["1", "2"]])
        ws2 = _make_worksheet("Other", [["X", "Y"], ["3", "4"]])

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["MySheet", "Other"]
        mock_wb.__getitem__ = MagicMock(side_effect=lambda name: ws1 if name == "MySheet" else ws2)
        mock_wb.close = MagicMock()

        mock_openpyxl = MagicMock()
        mock_openpyxl.load_workbook.return_value = mock_wb

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = self.ext.extract("test.xlsx")

        assert "## Sheet: MySheet" in result.markdown_text
        assert "## Sheet: Other" in result.markdown_text

    def test_skip_empty_rows(self):
        """Empty rows (all None) should not be counted."""
        ws = _make_worksheet("Sheet1", [["A", "B"], [None, None], ["1", "2"]])

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=ws)
        mock_wb.close = MagicMock()

        mock_openpyxl = MagicMock()
        mock_openpyxl.load_workbook.return_value = mock_wb

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = self.ext.extract("test.xlsx")

        assert result.metadata["Total rows"] == 2  # header + data, not the empty row

    def test_markdown_table_format(self):
        """Test proper markdown table formatting."""
        ws = _make_worksheet("Sheet1", [["A", "B"], ["1", "2"]])

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=ws)
        mock_wb.close = MagicMock()

        mock_openpyxl = MagicMock()
        mock_openpyxl.load_workbook.return_value = mock_wb

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = self.ext.extract("test.xlsx")

        assert "| A | B |" in result.markdown_text
        assert "| --- | --- |" in result.markdown_text
        assert "| 1 | 2 |" in result.markdown_text

    def test_file_not_found(self):
        with pytest.raises(ExtractionError):
            self.ext.extract("/nonexistent/file.xlsx")
