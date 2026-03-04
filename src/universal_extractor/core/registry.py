"""ExtractorRegistry — maps extensions and URL patterns to extractor classes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseExtractor

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """Registry that maps file extensions and URL patterns to extractors.

    Gracefully degrades: if a dependency is missing, logs a warning and skips
    the extractor (unavailable, not an error).
    """

    def __init__(self) -> None:
        self._by_extension: dict[str, BaseExtractor] = {}
        self._by_url_pattern: dict[str, BaseExtractor] = {}
        self._registered: list[BaseExtractor] = []

    def register(self, extractor: BaseExtractor) -> bool:
        """Register an extractor instance. Returns False if dependencies are missing."""
        ok, msg = extractor.check_dependencies()
        if not ok:
            logger.warning(
                "Skipping %s: %s", extractor.__class__.__name__, msg
            )
            return False

        for ext in extractor.supported_extensions:
            self._by_extension[ext.lower()] = extractor

        for pattern in extractor.supported_url_patterns:
            self._by_url_pattern[pattern.lower()] = extractor

        self._registered.append(extractor)
        logger.debug("Registered %s", extractor.__class__.__name__)
        return True

    def get_for_file(self, path: str) -> BaseExtractor | None:
        """Find an extractor for the given file path by extension."""
        path_lower = path.lower()
        for ext, extractor in self._by_extension.items():
            if path_lower.endswith(ext):
                return extractor
        return None

    def get_for_url(self, url: str) -> BaseExtractor | None:
        """Find an extractor for the given URL by pattern matching."""
        url_lower = url.lower()
        for pattern, extractor in self._by_url_pattern.items():
            if pattern in url_lower:
                return extractor
        return None

    def get(self, source: str) -> BaseExtractor | None:
        """Find an extractor for a file path or URL."""
        if source.startswith(("http://", "https://")):
            return self.get_for_url(source) or self.get_for_file(source)
        return self.get_for_file(source)

    def list_extractors(self) -> list[dict[str, str | set[str]]]:
        """Return info about all registered extractors."""
        result = []
        for ext in self._registered:
            result.append({
                "name": ext.__class__.__name__,
                "extensions": ext.supported_extensions,
                "url_patterns": ext.supported_url_patterns,
            })
        return result

    @property
    def registered_count(self) -> int:
        return len(self._registered)
