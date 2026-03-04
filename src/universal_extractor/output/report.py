"""BatchReport — summary statistics for batch extractions."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.base import ExtractionResult


@dataclass
class BatchReport:
    """Summary statistics for a batch extraction run."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_chars: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def add(self, result: ExtractionResult) -> None:
        """Add a result to the report."""
        self.total += 1
        if result.error:
            self.failed += 1
            self.errors.append((result.source, result.error))
        else:
            self.succeeded += 1
            self.total_chars += result.char_count
            self.by_type[result.source_type] = self.by_type.get(result.source_type, 0) + 1

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Processed: {self.total} files",
            f"Succeeded: {self.succeeded}",
            f"Failed: {self.failed}",
            f"Total characters: {self.total_chars:,}",
        ]

        if self.by_type:
            lines.append("By type:")
            for stype, count in sorted(self.by_type.items()):
                lines.append(f"  {stype}: {count}")

        if self.errors:
            lines.append("Errors:")
            for source, error in self.errors:
                lines.append(f"  {source}: {error}")

        return "\n".join(lines)
