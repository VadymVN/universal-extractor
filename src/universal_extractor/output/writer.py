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

        # Prefer title from metadata (e.g. YouTube video title)
        title = (result.metadata or {}).get("Title", "")
        if title:
            name = sanitize_filename(title)
        elif source.startswith(("http://", "https://")):
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

    def write(self, result: ExtractionResult, skip_existing: bool = False) -> Path | None:
        """Write a single result to a file. Returns the output path.

        If skip_existing is True and the file already exists, skip writing
        and return None.
        """
        filename = self._make_filename(result)
        path = self.output_dir / filename

        if skip_existing and path.exists():
            logger.info("Already exists, skipping: %s", path)
            return None

        path = self._resolve_path(filename)
        content = self._render(result)
        atomic_write(str(path), content)
        logger.info("Saved: %s", path)
        return path

    def write_batch(
        self, results: list[ExtractionResult], skip_existing: bool = False
    ) -> list[Path]:
        """Write multiple results. Returns list of output paths."""
        paths = []
        for result in results:
            if result.error and not result.text:
                logger.warning("Skipping failed extraction: %s", result.source)
                continue
            path = self.write(result, skip_existing=skip_existing)
            if path is not None:
                paths.append(path)
        return paths

    def write_batch_to_subdir(
        self, results: list[ExtractionResult], subdir_name: str,
        skip_existing: bool = False,
    ) -> tuple[Path, list[Path]]:
        """Write multiple results into a named subdirectory.

        Creates output_dir/subdir_name/ and writes all results there.
        Returns (subdir_path, [file_paths]).
        """
        safe_name = sanitize_filename(subdir_name)
        subdir = self.output_dir / safe_name
        subdir.mkdir(parents=True, exist_ok=True)

        sub_writer = OutputWriter(str(subdir), fmt=self.fmt)
        paths = sub_writer.write_batch(results, skip_existing=skip_existing)
        return subdir, paths
