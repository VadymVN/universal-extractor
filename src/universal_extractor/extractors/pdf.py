"""PDFExtractor — extracts text from PDF files using pdfplumber."""

from __future__ import annotations

from typing import Any, ClassVar

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
        pages_md: list[str] = []
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
                    pages_md.append(self._page_to_markdown(page))
        except Exception as e:
            raise ExtractionError(f"Failed to extract PDF {source}: {e}", source=source, cause=e)

        full_text = "\n\n".join(pages_text)
        markdown_text = "\n\n".join(part for part in pages_md if part)

        return ExtractionResult(
            text=full_text,
            source=source,
            source_type="pdf",
            extractor_name=self.__class__.__name__,
            metadata=metadata,
            markdown_text=markdown_text or None,
        )

    @staticmethod
    def _page_to_markdown(page: Any) -> str:
        """Convert a single PDF page to markdown, rendering tables inline."""
        parts: list[str] = []
        text = page.extract_text()
        tables = page.extract_tables()

        if tables:
            # Add page text first, then tables
            if text:
                parts.append(text)
            for table in tables:
                md_table = PDFExtractor._table_to_markdown(table)
                if md_table:
                    parts.append(md_table)
        elif text:
            parts.append(text)

        return "\n\n".join(parts)

    @staticmethod
    def _table_to_markdown(table: list[list[str | None]]) -> str:
        """Render a table as markdown."""
        if not table or len(table) < 2:
            return ""

        def cell(val: str | None) -> str:
            return (val or "").replace("|", "\\|").replace("\n", " ").strip()

        header = table[0]
        cols = len(header)
        lines = [
            "| " + " | ".join(cell(c) for c in header) + " |",
            "| " + " | ".join("---" for _ in range(cols)) + " |",
        ]
        for row in table[1:]:
            # Pad row to match header columns
            padded = list(row) + [None] * (cols - len(row))
            lines.append("| " + " | ".join(cell(c) for c in padded[:cols]) + " |")
        return "\n".join(lines)
