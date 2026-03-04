"""Tests for WebPageExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.webpage import WebPageExtractor


class TestWebPageExtractor:
    def setup_method(self):
        self.ext = WebPageExtractor()

    def test_can_handle_urls(self):
        assert self.ext.can_handle("https://example.com/article")
        assert self.ext.can_handle("http://example.com")
        assert not self.ext.can_handle("https://youtube.com/watch?v=abc")
        assert not self.ext.can_handle("https://youtu.be/abc")
        assert not self.ext.can_handle("document.pdf")

    def test_extract_mocked(self):
        mock_trafilatura = MagicMock()
        mock_trafilatura.fetch_url.return_value = "<html><body>Hello world</body></html>"
        # First call: plain text, second: markdown, third: JSON metadata
        mock_trafilatura.extract.side_effect = [
            "Hello world extracted text",
            "# Hello world markdown",
            '{"title": "Test Page", "author": "Test Author"}',
        ]

        with patch.dict(sys.modules, {"trafilatura": mock_trafilatura}):
            result = self.ext.extract("https://example.com/article")

        assert result.text == "Hello world extracted text"
        assert result.markdown_text == "# Hello world markdown"
        assert result.source_type == "webpage"
        assert result.metadata.get("Title") == "Test Page"

    def test_extract_no_content(self):
        mock_trafilatura = MagicMock()
        mock_trafilatura.fetch_url.return_value = None

        with patch.dict(sys.modules, {"trafilatura": mock_trafilatura}):
            with pytest.raises(ExtractionError, match="No content"):
                self.ext.extract("https://empty.com")

    def test_extract_no_text(self):
        mock_trafilatura = MagicMock()
        mock_trafilatura.fetch_url.return_value = "<html></html>"
        mock_trafilatura.extract.return_value = None

        with patch.dict(sys.modules, {"trafilatura": mock_trafilatura}):
            with pytest.raises(ExtractionError, match="Could not extract"):
                self.ext.extract("https://notext.com")
