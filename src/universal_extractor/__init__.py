"""Universal Extractor — extract text from any file or URL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import Config
from .core.base import ExtractionError, ExtractionResult
from .core.registry import ExtractorRegistry
from .core.router import InputRouter
from .extractors import register_all
from .output.writer import OutputWriter

if TYPE_CHECKING:
    from pathlib import Path

__version__ = "0.2.0"
__all__ = [
    "extract",
    "extract_batch",
    "extract_playlist",
    "save_result",
    "Config",
    "ExtractionResult",
    "ExtractionError",
]


def _build_router(config: Config | None = None) -> InputRouter:
    """Build a configured router with all available extractors."""
    registry = ExtractorRegistry()
    register_all(registry)
    return InputRouter(registry)


def extract(source: str, config: Config | None = None) -> ExtractionResult:
    """Extract text from a single file or URL.

    >>> from universal_extractor import extract
    >>> result = extract("document.pdf")
    >>> print(result.text)
    """
    router = _build_router(config)
    return router.extract(source)


def extract_batch(
    directory: str, config: Config | None = None
) -> list[ExtractionResult]:
    """Extract text from all supported files in a directory.

    >>> from universal_extractor import extract_batch
    >>> results = extract_batch("./documents/")
    """
    router = _build_router(config)
    return router.extract_directory(directory)


def extract_playlist(
    url: str,
    config: Config | None = None,
    skip_urls: set[str] | None = None,
) -> tuple[str, list[ExtractionResult]]:
    """Extract transcripts from all videos in a YouTube playlist.

    Args:
        url: YouTube playlist URL.
        config: Optional extraction config.
        skip_urls: Set of video URLs to skip (e.g. already processed).

    Returns (playlist_title, [ExtractionResult, ...]).

    >>> from universal_extractor import extract_playlist
    >>> title, results = extract_playlist("https://youtube.com/playlist?list=PLxxx")
    """
    router = _build_router(config)
    return router.extract_playlist(url, skip_urls=skip_urls)


def save_result(
    result: ExtractionResult, output_dir: str = "output", fmt: str = "md"
) -> Path:
    """Save an extraction result to a file.

    >>> from universal_extractor import extract, save_result
    >>> result = extract("document.pdf")
    >>> path = save_result(result, "output/")
    """
    writer = OutputWriter(output_dir, fmt=fmt)
    return writer.write(result)
