"""DocxExtractor — extracts text from DOCX files using python-docx."""

from __future__ import annotations

from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult


class DocxExtractor(BaseExtractor):
    """Extracts text from DOCX files using python-docx."""

    supported_extensions: ClassVar[set[str]] = {".docx"}
    required_packages: ClassVar[set[str]] = {"docx"}

    def extract(self, source: str) -> ExtractionResult:
        try:
            from docx import Document
        except ImportError as e:
            raise ExtractionError(
                "python-docx is required for DOCX extraction: pip install python-docx",
                source=source,
                cause=e,
            )

        try:
            doc = Document(source)
        except Exception as e:
            raise ExtractionError(
                f"Failed to open DOCX {source}: {e}", source=source, cause=e
            )

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)

        metadata: dict = {}
        core = doc.core_properties
        if core.author:
            metadata["Author"] = core.author
        if core.title:
            metadata["Title"] = core.title
        if core.subject:
            metadata["Subject"] = core.subject

        return ExtractionResult(
            text=full_text,
            source=source,
            source_type="docx",
            extractor_name=self.__class__.__name__,
            metadata=metadata,
        )
