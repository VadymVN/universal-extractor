"""InputRouter — classifies input and dispatches to the correct extractor."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from .base import BaseExtractor, ExtractionError, ExtractionResult
from .registry import ExtractorRegistry
from ..utils.sanitize import is_url

logger = logging.getLogger(__name__)


class InputRouter:
    """Routes input sources (file, directory, URL) to appropriate extractors."""

    def __init__(self, registry: ExtractorRegistry) -> None:
        self.registry = registry

    def classify(self, source: str) -> str:
        """Classify input as 'url', 'file', or 'directory'."""
        if is_url(source):
            return "url"
        path = Path(source)
        if path.is_dir():
            return "directory"
        if path.is_file():
            return "file"
        raise ExtractionError(f"Source not found or unsupported: {source}", source=source)

    def resolve_extractor(self, source: str) -> BaseExtractor:
        """Find the right extractor for a source."""
        extractor = self.registry.get(source)
        if extractor is not None:
            return extractor

        # Try MIME type as fallback for files without recognized extensions
        if not is_url(source):
            mime_type, _ = mimetypes.guess_type(source)
            if mime_type and mime_type.startswith("text/"):
                text_ext = self.registry.get_for_file("file.txt")
                if text_ext is not None:
                    return text_ext

        raise ExtractionError(
            f"No extractor available for: {source}",
            source=source,
        )

    def extract(self, source: str) -> ExtractionResult:
        """Extract text from a single source."""
        extractor = self.resolve_extractor(source)
        return extractor.extract(source)

    def extract_directory(self, directory: str) -> list[ExtractionResult]:
        """Extract text from all supported files in a directory (recursive)."""
        results: list[ExtractionResult] = []
        dir_path = Path(directory)

        files = sorted(dir_path.rglob("*"))
        for file_path in files:
            if not file_path.is_file():
                continue
            source = str(file_path)
            try:
                extractor = self.registry.get(source)
                if extractor is None:
                    continue
                result = extractor.extract(source)
                results.append(result)
            except Exception as e:
                logger.error("Failed to extract %s: %s", source, e)
                results.append(
                    ExtractionResult(
                        text="",
                        source=source,
                        source_type="unknown",
                        extractor_name="none",
                        error=str(e),
                    )
                )
        return results
