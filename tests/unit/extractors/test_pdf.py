"""Tests for PDFExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.extractors.pdf import PDFExtractor
from universal_extractor.core.base import ExtractionError


class TestPDFExtractor:
    def setup_method(self):
        self.ext = PDFExtractor()

    def test_can_handle(self):
        assert self.ext.can_handle("document.pdf")
        assert self.ext.can_handle("DOCUMENT.PDF")
        assert not self.ext.can_handle("document.docx")

    def test_extract_mocked(self):
        """Test extraction with mocked pdfplumber."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text content"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.metadata = {"Author": "Test Author", "Title": "Test Doc"}
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
            result = self.ext.extract("test.pdf")

        assert result.text == "Page 1 text content"
        assert result.source_type == "pdf"
        assert result.metadata.get("Author") == "Test Author"

    def test_file_not_found(self):
        with pytest.raises(ExtractionError):
            self.ext.extract("/nonexistent/file.pdf")
