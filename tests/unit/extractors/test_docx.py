"""Tests for DocxExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.docx import DocxExtractor


class TestDocxExtractor:
    def setup_method(self):
        self.ext = DocxExtractor()

    def test_can_handle(self):
        assert self.ext.can_handle("document.docx")
        assert self.ext.can_handle("REPORT.DOCX")
        assert not self.ext.can_handle("document.pdf")
        assert not self.ext.can_handle("document.doc")

    def _make_mock_para(self, text, style_name="Normal", bold=False, italic=False):
        """Helper to create a mock paragraph."""
        mock_run = MagicMock()
        mock_run.text = text
        mock_run.bold = bold
        mock_run.italic = italic

        mock_style = MagicMock()
        mock_style.name = style_name

        mock_para = MagicMock()
        mock_para.text = text
        mock_para.style = mock_style
        mock_para.runs = [mock_run]
        return mock_para

    def test_extract_mocked(self):
        """Test extraction with mocked python-docx."""
        mock_para1 = self._make_mock_para("First paragraph")
        mock_para2 = self._make_mock_para("Second paragraph")
        mock_para3 = MagicMock()
        mock_para3.text = "  "  # Whitespace-only, should be skipped
        mock_para3.style = MagicMock()
        mock_para3.style.name = "Normal"
        mock_para3.runs = []

        mock_core = MagicMock()
        mock_core.author = "Test Author"
        mock_core.title = "Test Title"
        mock_core.subject = None

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.core_properties = mock_core

        mock_docx_module = MagicMock()
        mock_docx_module.Document.return_value = mock_doc

        with patch.dict(sys.modules, {"docx": mock_docx_module}):
            result = self.ext.extract("test.docx")

        assert result.text == "First paragraph\n\nSecond paragraph"
        assert result.source_type == "docx"
        assert result.metadata["Author"] == "Test Author"
        assert result.metadata["Title"] == "Test Title"
        assert "Subject" not in result.metadata

    def test_markdown_headings_and_bold(self):
        """Test that heading styles and bold runs produce markdown."""
        mock_heading = self._make_mock_para("Title", style_name="Heading 1")
        mock_bold = self._make_mock_para("Important", bold=True)

        mock_core = MagicMock()
        mock_core.author = None
        mock_core.title = None
        mock_core.subject = None

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_heading, mock_bold]
        mock_doc.core_properties = mock_core

        mock_docx_module = MagicMock()
        mock_docx_module.Document.return_value = mock_doc

        with patch.dict(sys.modules, {"docx": mock_docx_module}):
            result = self.ext.extract("test.docx")

        assert result.markdown_text is not None
        assert "# Title" in result.markdown_text
        assert "**Important**" in result.markdown_text

    def test_file_not_found(self):
        with pytest.raises(ExtractionError):
            self.ext.extract("/nonexistent/file.docx")
