"""Tests for OutputWriter and BatchReport."""

from pathlib import Path

import pytest

from universal_extractor.core.base import ExtractionResult
from universal_extractor.output.writer import OutputWriter
from universal_extractor.output.report import BatchReport


@pytest.fixture
def tmp_output(tmp_path):
    return OutputWriter(str(tmp_path))


@pytest.fixture
def sample_result():
    return ExtractionResult(
        text="Hello world",
        source="/path/to/document.pdf",
        source_type="pdf",
        extractor_name="PDFExtractor",
        metadata={"Pages": 5},
    )


class TestOutputWriter:
    def test_write_creates_file(self, tmp_output, sample_result):
        path = tmp_output.write(sample_result)
        assert path.exists()
        content = path.read_text()
        assert "Hello world" in content
        assert "Source: /path/to/document.pdf" in content
        assert "Type: pdf" in content

    def test_write_dedup_filename(self, tmp_output, sample_result):
        path1 = tmp_output.write(sample_result)
        path2 = tmp_output.write(sample_result)
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_write_url_source(self, tmp_output):
        result = ExtractionResult(
            text="Web content",
            source="https://example.com/article/my-post",
            source_type="webpage",
            extractor_name="WebPageExtractor",
        )
        path = tmp_output.write(result)
        assert "my-post" in path.name

    def test_write_batch(self, tmp_output, sample_result):
        results = [sample_result, sample_result]
        paths = tmp_output.write_batch(results)
        assert len(paths) == 2

    def test_write_batch_skips_failed(self, tmp_output):
        failed = ExtractionResult(
            text="",
            source="bad.pdf",
            source_type="pdf",
            extractor_name="PDFExtractor",
            error="Failed to read",
        )
        paths = tmp_output.write_batch([failed])
        assert len(paths) == 0


class TestBatchReport:
    def test_report_counts(self):
        report = BatchReport()
        report.add(ExtractionResult(
            text="ok", source="a.txt", source_type="txt", extractor_name="X"
        ))
        report.add(ExtractionResult(
            text="", source="b.pdf", source_type="pdf", extractor_name="Y",
            error="fail"
        ))
        assert report.total == 2
        assert report.succeeded == 1
        assert report.failed == 1
        assert report.by_type == {"txt": 1}

    def test_summary_output(self):
        report = BatchReport()
        report.add(ExtractionResult(
            text="hello", source="a.txt", source_type="txt", extractor_name="X"
        ))
        summary = report.summary()
        assert "Processed: 1" in summary
        assert "Succeeded: 1" in summary
