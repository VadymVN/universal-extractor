"""OutputWriter — saves ExtractionResults with format-dependent rendering."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.base import ExtractionResult
from ..utils.io import atomic_write
from ..utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)

_EXT_MAP = {"md": ".md", "txt": ".txt", "json": ".json"}


class OutputWriter:
    """Writes extraction results to files with YAML-style metadata headers."""

    def __init__(self, output_dir: str = "output", fmt: str = "md") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fmt = fmt

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
        ext = _EXT_MAP.get(self.fmt, ".md")
        return f"{name}{ext}"

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

    def _render(self, result: ExtractionResult) -> str:
        """Render result content based on output format."""
        if self.fmt == "json":
            return result.to_json()
        if self.fmt == "txt":
            return result.to_header() + "\n\n" + result.text
        # md (default): prefer markdown_text if available
        body = result.markdown_text or result.text
        return result.to_header() + "\n\n" + body

    def write(self, result: ExtractionResult) -> Path:
        """Write a single result to a file. Returns the output path."""
        filename = self._make_filename(result)
        path = self._resolve_path(filename)

        content = self._render(result)
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
