"""Tests for PptxExtractor."""

import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.pptx import PptxExtractor


def _make_paragraph(text: str, level: int = 0) -> MagicMock:
    para = MagicMock()
    para.text = text
    type(para).level = PropertyMock(return_value=level)
    para.strip = MagicMock(return_value=text.strip())
    return para


def _make_text_frame(paragraphs: list[MagicMock]) -> MagicMock:
    tf = MagicMock()
    tf.paragraphs = paragraphs
    return tf


def _make_shape(text_frame=None, table=None) -> MagicMock:
    shape = MagicMock()
    shape.has_text_frame = text_frame is not None
    shape.has_table = table is not None
    if text_frame:
        shape.text_frame = text_frame
    if table:
        shape.table = table
    return shape


def _make_table(rows_data: list[list[str]]) -> MagicMock:
    table = MagicMock()
    rows = []
    for row_data in rows_data:
        row = MagicMock()
        cells = []
        for val in row_data:
            cell = MagicMock()
            cell.text = val
            cells.append(cell)
        row.cells = cells
        rows.append(row)
    table.rows = rows
    return table


def _make_slide(shapes: list[MagicMock]) -> MagicMock:
    slide = MagicMock()
    slide.shapes = shapes
    return slide


class TestPptxExtractor:
    def setup_method(self):
        self.ext = PptxExtractor()

    def test_can_handle(self):
        assert self.ext.can_handle("presentation.pptx")
        assert self.ext.can_handle("PRESENTATION.PPTX")
        assert not self.ext.can_handle("document.ppt")
        assert not self.ext.can_handle("document.pdf")

    def test_extract_mocked(self):
        """Test extraction with mocked python-pptx."""
        para1 = _make_paragraph("Hello World")
        tf = _make_text_frame([para1])
        shape = _make_shape(text_frame=tf)
        slide = _make_slide([shape])

        mock_prs = MagicMock()
        mock_prs.slides = [slide]
        mock_prs.core_properties.author = "Test Author"
        mock_prs.core_properties.title = "Test Presentation"

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs

        with patch.dict(sys.modules, {"pptx": mock_pptx}):
            result = self.ext.extract("test.pptx")

        assert result.text == "Hello World"
        assert result.source_type == "pptx"
        assert result.metadata["Author"] == "Test Author"
        assert result.metadata["Title"] == "Test Presentation"
        assert result.metadata["Slides"] == 1

    def test_markdown_slide_headers(self):
        """Test that slides get ## Slide N headers in markdown."""
        para1 = _make_paragraph("Slide one content")
        para2 = _make_paragraph("Slide two content")
        slide1 = _make_slide([_make_shape(text_frame=_make_text_frame([para1]))])
        slide2 = _make_slide([_make_shape(text_frame=_make_text_frame([para2]))])

        mock_prs = MagicMock()
        mock_prs.slides = [slide1, slide2]
        mock_prs.core_properties.author = None
        mock_prs.core_properties.title = None

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs

        with patch.dict(sys.modules, {"pptx": mock_pptx}):
            result = self.ext.extract("test.pptx")

        assert "## Slide 1" in result.markdown_text
        assert "## Slide 2" in result.markdown_text
        assert "Slide one content" in result.markdown_text
        assert "Slide two content" in result.markdown_text

    def test_table_markdown(self):
        """Test table rendering in markdown."""
        table = _make_table([["Name", "Age"], ["Alice", "30"], ["Bob", "25"]])
        shape = _make_shape(table=table)
        slide = _make_slide([shape])

        mock_prs = MagicMock()
        mock_prs.slides = [slide]
        mock_prs.core_properties.author = None
        mock_prs.core_properties.title = None

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs

        with patch.dict(sys.modules, {"pptx": mock_pptx}):
            result = self.ext.extract("test.pptx")

        assert "| Name | Age |" in result.markdown_text
        assert "| --- | --- |" in result.markdown_text
        assert "| Alice | 30 |" in result.markdown_text

    def test_bullet_levels(self):
        """Test bullet indentation for nested paragraphs."""
        para0 = _make_paragraph("Top level")
        para1 = _make_paragraph("Sub item", level=1)
        tf = _make_text_frame([para0, para1])
        slide = _make_slide([_make_shape(text_frame=tf)])

        mock_prs = MagicMock()
        mock_prs.slides = [slide]
        mock_prs.core_properties.author = None
        mock_prs.core_properties.title = None

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs

        with patch.dict(sys.modules, {"pptx": mock_pptx}):
            result = self.ext.extract("test.pptx")

        assert "  - Sub item" in result.markdown_text

    def test_file_not_found(self):
        with pytest.raises(ExtractionError):
            self.ext.extract("/nonexistent/file.pptx")
