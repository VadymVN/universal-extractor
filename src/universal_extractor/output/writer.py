"""OutputWriter — saves ExtractionResults as text files with metadata headers."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.base import ExtractionResult
from ..utils.io import atomic_write
from ..utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)


class OutputWriter:
    """Writes extraction results to text files with YAML-style metadata headers."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _make_filename(self, result: ExtractionResult) -> str:
        """Generate output filename from the source path/URL."""
        source = result.source

        # For URLs, use the last meaningful path segment
        if source.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            parsed = urlparse(source)
            name = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
        else:
            name = Path(source).stem

        name = sanitize_filename(name)
        return f"{name}.txt"

    def _resolve_path(self, filename: str) -> Path:
        """Resolve output path, adding suffix if file exists."""
        path = self.output_dir / filename
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        counter = 1
        while path.exists():
            path = self.output_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        return path

    def write(self, result: ExtractionResult) -> Path:
        """Write a single result to a file. Returns the output path."""
        filename = self._make_filename(result)
        path = self._resolve_path(filename)

        content = result.to_header() + "\n\n" + result.text
        atomic_write(str(path), content)
        logger.info("Saved: %s", path)
        return path

    def write_batch(self, results: list[ExtractionResult]) -> list[Path]:
        """Write multiple results. Returns list of output paths."""
        paths = []
        for result in results:
            if result.error and not result.text:
                logger.warning("Skipping failed extraction: %s", result.source)
                continue
            path = self.write(result)
            paths.append(path)
        return paths
