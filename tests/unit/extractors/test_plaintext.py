"""Tests for PlainTextExtractor."""

from pathlib import Path

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.plaintext import PlainTextExtractor

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestPlainTextExtractor:
    def setup_method(self):
        self.ext = PlainTextExtractor()

    def test_extract_txt(self):
        result = self.ext.extract(str(FIXTURES / "sample.txt"))
        assert "sample text file" in result.text
        assert result.source_type == "txt"
        assert result.char_count > 0

    def test_extract_md(self):
        result = self.ext.extract(str(FIXTURES / "sample.md"))
        assert "Sample Markdown" in result.text
        assert result.source_type == "md"

    def test_unicode_content(self):
        result = self.ext.extract(str(FIXTURES / "sample.txt"))
        assert "Привет мир!" in result.text

    def test_can_handle(self):
        assert self.ext.can_handle("file.txt")
        assert self.ext.can_handle("file.md")
        assert self.ext.can_handle("file.csv")
        assert not self.ext.can_handle("file.pdf")

    def test_file_not_found(self):
        with pytest.raises(ExtractionError):
            self.ext.extract("/nonexistent/file.txt")

    def test_to_header(self):
        result = self.ext.extract(str(FIXTURES / "sample.txt"))
        header = result.to_header()
        assert "Source:" in header
        assert "Type: txt" in header
        assert "Characters:" in header
