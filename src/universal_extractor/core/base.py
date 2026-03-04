"""Core abstractions: ExtractionResult, BaseExtractor, ExtractionError."""

from __future__ import annotations

import importlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar


class ExtractionError(Exception):
    """Raised when extraction fails."""

    def __init__(self, message: str, source: str = "", cause: Exception | None = None):
        self.source = source
        self.cause = cause
        super().__init__(message)


@dataclass
class ExtractionResult:
    """Unified result returned by all extractors."""

    text: str
    source: str
    source_type: str
    extractor_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    language: str | None = None
    char_count: int = 0
    error: str | None = None
    markdown_text: str | None = None

    def __post_init__(self) -> None:
        if self.char_count == 0 and self.text:
            self.char_count = len(self.text)

    def to_header(self) -> str:
        """Generate YAML-style metadata header for output files."""
        lines = [
            "---",
            f"Source: {self.source}",
            f"Type: {self.source_type}",
            f"Extracted: {self.extracted_at.strftime('%Y-%m-%dT%H:%M:%S')}",
        ]
        if self.language:
            lines.append(f"Language: {self.language}")
        lines.append(f"Characters: {self.char_count}")

        for key, value in self.metadata.items():
            if value is not None:
                lines.append(f"{key}: {value}")

        lines.append("---")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize result to JSON."""
        data: dict[str, Any] = {
            "source": self.source,
            "source_type": self.source_type,
            "extractor_name": self.extractor_name,
            "extracted_at": self.extracted_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "language": self.language,
            "char_count": self.char_count,
            "metadata": self.metadata,
            "text": self.text,
        }
        if self.markdown_text is not None:
            data["markdown_text"] = self.markdown_text
        if self.error:
            data["error"] = self.error
        return json.dumps(data, ensure_ascii=False, indent=2)


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    supported_extensions: ClassVar[set[str]] = set()
    supported_url_patterns: ClassVar[set[str]] = set()
    required_packages: ClassVar[set[str]] = set()

    @abstractmethod
    def extract(self, source: str) -> ExtractionResult:
        """Extract text from the given source path or URL."""

    def can_handle(self, source: str) -> bool:
        """Check if this extractor can handle the given source."""
        source_lower = source.lower()

        for ext in self.supported_extensions:
            if source_lower.endswith(ext):
                return True

        for pattern in self.supported_url_patterns:
            if pattern in source_lower:
                return True

        return False

    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Verify that all required packages are importable."""
        missing = []
        for package in cls.required_packages:
            try:
                importlib.import_module(package)
            except ImportError:
                missing.append(package)

        if missing:
            return False, f"Missing packages: {', '.join(missing)}"
        return True, ""
