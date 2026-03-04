"""Tests for ExtractorRegistry."""

from universal_extractor.core.base import BaseExtractor, ExtractionResult
from universal_extractor.core.registry import ExtractorRegistry


class FakeExtractor(BaseExtractor):
    supported_extensions = {".fake"}
    supported_url_patterns = {"fake.com"}
    required_packages: set[str] = set()

    def extract(self, source: str) -> ExtractionResult:
        return ExtractionResult(
            text="fake", source=source, source_type="fake", extractor_name="FakeExtractor"
        )


class MissingDepsExtractor(BaseExtractor):
    supported_extensions = {".nope"}
    required_packages = {"nonexistent_package_xyz"}

    def extract(self, source: str) -> ExtractionResult:
        raise NotImplementedError


class TestExtractorRegistry:
    def test_register_and_lookup_by_extension(self):
        reg = ExtractorRegistry()
        ext = FakeExtractor()
        assert reg.register(ext) is True
        assert reg.get_for_file("document.fake") is ext

    def test_register_and_lookup_by_url(self):
        reg = ExtractorRegistry()
        ext = FakeExtractor()
        reg.register(ext)
        assert reg.get_for_url("https://fake.com/page") is ext

    def test_get_unified(self):
        reg = ExtractorRegistry()
        ext = FakeExtractor()
        reg.register(ext)
        assert reg.get("test.fake") is ext
        assert reg.get("https://fake.com/page") is ext

    def test_missing_extension_returns_none(self):
        reg = ExtractorRegistry()
        assert reg.get_for_file("test.xyz") is None

    def test_missing_deps_skips_registration(self):
        reg = ExtractorRegistry()
        assert reg.register(MissingDepsExtractor()) is False
        assert reg.registered_count == 0

    def test_list_extractors(self):
        reg = ExtractorRegistry()
        reg.register(FakeExtractor())
        info = reg.list_extractors()
        assert len(info) == 1
        assert info[0]["name"] == "FakeExtractor"

    def test_case_insensitive_lookup(self):
        reg = ExtractorRegistry()
        ext = FakeExtractor()
        reg.register(ext)
        assert reg.get_for_file("DOC.FAKE") is ext
