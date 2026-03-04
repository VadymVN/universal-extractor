"""Tests for InputRouter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from universal_extractor.core.base import BaseExtractor, ExtractionError, ExtractionResult
from universal_extractor.core.registry import ExtractorRegistry
from universal_extractor.core.router import InputRouter

FIXTURES = Path(__file__).parent.parent / "fixtures"


class FakeExtractor(BaseExtractor):
    supported_extensions = {".txt", ".md"}
    required_packages: set[str] = set()

    def extract(self, source: str) -> ExtractionResult:
        return ExtractionResult(
            text="extracted",
            source=source,
            source_type="txt",
            extractor_name="FakeExtractor",
        )


class TestInputRouter:
    def setup_method(self):
        self.registry = ExtractorRegistry()
        self.registry.register(FakeExtractor())
        self.router = InputRouter(self.registry)

    def test_classify_file(self):
        assert self.router.classify(str(FIXTURES / "sample.txt")) == "file"

    def test_classify_directory(self):
        assert self.router.classify(str(FIXTURES)) == "directory"

    def test_classify_url(self):
        assert self.router.classify("https://example.com") == "url"

    def test_classify_nonexistent(self):
        with pytest.raises(ExtractionError):
            self.router.classify("/nonexistent/path")

    def test_resolve_extractor(self):
        ext = self.router.resolve_extractor(str(FIXTURES / "sample.txt"))
        assert isinstance(ext, FakeExtractor)

    def test_resolve_no_extractor(self):
        with pytest.raises(ExtractionError, match="No extractor"):
            self.router.resolve_extractor(str(FIXTURES / "sample.xyz"))

    def test_extract_single(self):
        result = self.router.extract(str(FIXTURES / "sample.txt"))
        assert result.text == "extracted"

    def test_extract_directory(self):
        results = self.router.extract_directory(str(FIXTURES))
        # Should find at least sample.txt and sample.md
        sources = [r.source for r in results]
        assert any("sample.txt" in s for s in sources)
        assert any("sample.md" in s for s in sources)
