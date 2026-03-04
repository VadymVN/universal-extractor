"""Extractor registration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.registry import ExtractorRegistry

logger = logging.getLogger(__name__)


def register_all(registry: ExtractorRegistry) -> None:
    """Register all available extractors with the registry."""
    from .plaintext import PlainTextExtractor
    from .pdf import PDFExtractor
    from .docx import DocxExtractor

    for extractor_cls in [PlainTextExtractor, PDFExtractor, DocxExtractor]:
        registry.register(extractor_cls())

    # Optional extractors — import errors are expected
    try:
        from .webpage import WebPageExtractor
        registry.register(WebPageExtractor())
    except ImportError:
        logger.debug("WebPageExtractor unavailable (missing trafilatura)")

    try:
        from .youtube import YouTubeExtractor
        registry.register(YouTubeExtractor())
    except ImportError:
        logger.debug("YouTubeExtractor unavailable (missing dependencies)")

    try:
        from .video import VideoExtractor
        registry.register(VideoExtractor())
    except ImportError:
        logger.debug("VideoExtractor unavailable (missing whisper/torch)")
