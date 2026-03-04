"""PDFExtractor — extracts text from PDF files using pdfplumber."""

from __future__ import annotations

from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF files using pdfplumber."""

    supported_extensions: ClassVar[set[str]] = {".pdf"}
    required_packages: ClassVar[set[str]] = {"pdfplumber"}

    def extract(self, source: str) -> ExtractionResult:
        try:
            import pdfplumber
        except ImportError as e:
            raise ExtractionError(
                "pdfplumber is required for PDF extraction: pip install pdfplumber",
                source=source,
                cause=e,
            )

        pages_text: list[str] = []
        metadata: dict = {}

        try:
            with pdfplumber.open(source) as pdf:
                metadata["pages"] = len(pdf.pages)
                if pdf.metadata:
                    for key in ("Author", "Title", "Subject", "Creator"):
                        val = pdf.metadata.get(key)
                        if val:
                            metadata[key] = val

                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
        except Exception as e:
            raise ExtractionError(f"Failed to extract PDF {source}: {e}", source=source, cause=e)

        full_text = "\n\n".join(pages_text)

        return ExtractionResult(
            text=full_text,
            source=source,
            source_type="pdf",
            extractor_name=self.__class__.__name__,
            metadata=metadata,
        )
