"""PlainTextExtractor — handles .txt, .md, .rst, .csv, .log files."""

from __future__ import annotations

from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult
from ..utils.io import read_text_file


class PlainTextExtractor(BaseExtractor):
    """Extracts text from plain text files with encoding detection."""

    supported_extensions: ClassVar[set[str]] = {
        ".txt", ".md", ".rst", ".csv", ".log", ".json", ".xml", ".yaml", ".yml",
        ".ini", ".cfg", ".conf", ".toml", ".env", ".sh", ".bash", ".zsh",
        ".py", ".js", ".ts", ".html", ".css",
    }
    required_packages: ClassVar[set[str]] = set()

    def extract(self, source: str) -> ExtractionResult:
        try:
            text = read_text_file(source)
        except FileNotFoundError:
            raise ExtractionError(f"File not found: {source}", source=source)
        except Exception as e:
            raise ExtractionError(f"Failed to read {source}: {e}", source=source, cause=e)

        # Determine sub-type from extension
        ext = "." + source.rsplit(".", 1)[-1].lower() if "." in source else ""
        source_type = ext.lstrip(".") if ext else "plaintext"

        return ExtractionResult(
            text=text,
            source=source,
            source_type=source_type,
            extractor_name=self.__class__.__name__,
            metadata={"encoding": "detected"},
        )
