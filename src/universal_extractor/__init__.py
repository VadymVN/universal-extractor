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

__version__ = "0.1.0"
__all__ = [
    "extract",
    "extract_batch",
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
