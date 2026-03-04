"""WebPageExtractor — extracts text from web pages using trafilatura."""

from __future__ import annotations

import logging
from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult

logger = logging.getLogger(__name__)


class WebPageExtractor(BaseExtractor):
    """Extracts main text content from web pages using trafilatura."""

    supported_extensions: ClassVar[set[str]] = set()
    supported_url_patterns: ClassVar[set[str]] = {"http://", "https://"}
    required_packages: ClassVar[set[str]] = {"trafilatura"}

    # URLs that should NOT be handled by this extractor
    _excluded_patterns = {"youtube.com", "youtu.be"}

    def can_handle(self, source: str) -> bool:
        source_lower = source.lower()
        # Exclude YouTube URLs
        for pattern in self._excluded_patterns:
            if pattern in source_lower:
                return False
        return source_lower.startswith(("http://", "https://"))

    def extract(self, source: str) -> ExtractionResult:
        try:
            import trafilatura
        except ImportError as e:
            raise ExtractionError(
                "trafilatura is required: pip install trafilatura",
                source=source,
                cause=e,
            )

        logger.info("Fetching web page: %s", source)

        try:
            downloaded = trafilatura.fetch_url(source)
        except Exception as e:
            raise ExtractionError(
                f"Failed to fetch {source}: {e}", source=source, cause=e
            )

        if not downloaded:
            raise ExtractionError(f"No content retrieved from {source}", source=source)

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )

        if not text:
            raise ExtractionError(
                f"Could not extract text from {source}", source=source
            )

        # Try to get metadata
        metadata: dict = {}
        try:
            meta = trafilatura.extract(
                downloaded,
                output_format="json",
                include_comments=False,
            )
            if meta:
                import json
                meta_dict = json.loads(meta)
                for key in ("title", "author", "date", "sitename"):
                    val = meta_dict.get(key)
                    if val:
                        metadata[key.capitalize()] = val
        except Exception:
            pass  # Metadata extraction is best-effort

        return ExtractionResult(
            text=text,
            source=source,
            source_type="webpage",
            extractor_name=self.__class__.__name__,
            metadata=metadata,
        )
